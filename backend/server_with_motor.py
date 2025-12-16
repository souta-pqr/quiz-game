#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
クイズゲーム用モーター制御統合サーバー
"""

import asyncio
import cv2
import json
import time
import os
import numpy as np
import torch
import base64
from typing import Set, Optional, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from vosk import Model, KaldiRecognizer
import threading

# GPIO制御のインポート（Raspberry Piの場合のみ）
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️ RPi.GPIOが利用できません。ダミーモードで動作します。")

# ===================================
# GPIO設定（Raspberry Pi用）
# ===================================
START_STOP = 24
RUN_BRAKE = 12
CW_CCW = 14
INT_VR_EXT = 1

ON = 0 if GPIO_AVAILABLE else None
OFF = 1 if GPIO_AVAILABLE else None

# ===================================
# モーター設定
# ===================================
HALF_ROTATION_TIME = 0.9
STEP_DURATION = 0.15
STEP_PAUSE = 0.75

# グローバル変数
active_connections: Set[WebSocket] = set()
detector = None
detection_running = False
motor_controller = None
vosk_model = None
vad_model = None
SAMPLE_RATE = 16000
audio_buffers = {}

# モーター状態管理
motor_state = {
    "is_running": False,
    "is_stopped_for_answer": False,
    "snapshot_image": None,
    "detection_timestamp": None
}
motor_state_lock = threading.RLock()


class MotorController:
    """BLHモーター制御クラス"""
    
    def __init__(self, half_rotation_time=HALF_ROTATION_TIME):
        self.is_initialized = False
        self._is_running = False
        self.direction = "STOP"
        self.half_rotation_time = half_rotation_time
        self.current_direction_cw = False
        self.rotation_start_time = None
        self.elapsed_time = 0.0
        self.rotation_interrupted = False
        self.lock = threading.RLock()
        self._emergency_stop_requested = False
        
        self.rotation_phase = "ccw_cycle"
        self.phase_count = 0
        self.total_rotations = 0
    
    @property
    def is_running(self):
        with self.lock:
            return self._is_running
    
    @is_running.setter
    def is_running(self, value):
        with self.lock:
            self._is_running = value
    
    def initialize(self):
        """モーター初期化"""
        print("🔧 モーター初期化中...")
        try:
            if GPIO_AVAILABLE:
                GPIO.output(START_STOP, OFF)
                GPIO.output(RUN_BRAKE, OFF)
                GPIO.output(CW_CCW, OFF)
                GPIO.output(INT_VR_EXT, ON)
                time.sleep(0.5)
            
            with self.lock:
                self.is_initialized = True
                self._is_running = False
                self.rotation_phase = "ccw_cycle"
                self.current_direction_cw = False
                self.phase_count = 0
                self.total_rotations = 0
            
            print("✓ モーター初期化完了")
        except Exception as e:
            print(f"❌ モーター初期化エラー: {e}")
            raise
    
    def _execute_step_with_check(self, is_cw):
        """ステップ実行（緊急停止チェック付き）"""
        with self.lock:
            if self._emergency_stop_requested:
                return False
        
        try:
            if GPIO_AVAILABLE:
                GPIO.output(CW_CCW, ON if is_cw else OFF)
                time.sleep(0.01)
                GPIO.output(START_STOP, ON)
                time.sleep(0.01)
                GPIO.output(RUN_BRAKE, ON)
            
            # 回転時間
            rotation_steps = 6
            step_interval = STEP_DURATION / rotation_steps
            
            for i in range(rotation_steps):
                with self.lock:
                    if self._emergency_stop_requested:
                        if GPIO_AVAILABLE:
                            GPIO.output(RUN_BRAKE, OFF)
                            time.sleep(0.01)
                            GPIO.output(START_STOP, OFF)
                        return False
                time.sleep(step_interval)
            
            if GPIO_AVAILABLE:
                GPIO.output(RUN_BRAKE, OFF)
                time.sleep(0.01)
                GPIO.output(START_STOP, OFF)
            
            # 停止時間
            pause_steps = 10
            pause_interval = STEP_PAUSE / pause_steps
            
            for i in range(pause_steps):
                with self.lock:
                    if self._emergency_stop_requested:
                        return False
                time.sleep(pause_interval)
            
            return True
            
        except Exception as e:
            print(f"❌ ステップ実行エラー: {e}")
            return False
    
    def start_slow_rotation(self):
        """断続運転開始"""
        with self.lock:
            if not self.is_initialized or self._is_running:
                return False
            
            direction_str = "CW" if self.current_direction_cw else "CCW"
            print(f"▶ {direction_str}断続運転開始")
            
            self._is_running = True
            self._emergency_stop_requested = False
            self.direction = direction_str
            self.rotation_start_time = time.time()
            self.elapsed_time = 0.0
            return True
    
    def execute_one_step(self):
        """1ステップ実行"""
        with self.lock:
            if not self._is_running:
                return False
            
            if self._emergency_stop_requested:
                self._perform_emergency_stop()
                return False
        
        try:
            step_start = time.time()
            success = self._execute_step_with_check(self.current_direction_cw)
            
            if not success:
                with self.lock:
                    self._perform_emergency_stop()
                return False
            
            step_time = time.time() - step_start
            
            with self.lock:
                self.elapsed_time += step_time
            return True
        except Exception as e:
            print(f"❌ ステップ実行中エラー: {e}")
            with self.lock:
                self._is_running = False
            return False
    
    def check_rotation_complete(self):
        """半回転完了チェック"""
        with self.lock:
            if not self._is_running:
                return False
            return self.elapsed_time >= self.half_rotation_time
    
    def request_emergency_stop(self):
        """緊急停止リクエスト"""
        with self.lock:
            if not self._is_running:
                return
            print(f"🚨 緊急停止リクエスト受信")
            self._emergency_stop_requested = True
    
    def _perform_emergency_stop(self):
        """緊急停止実行"""
        try:
            print(f"🛑 緊急停止実行中...")
            
            if GPIO_AVAILABLE:
                GPIO.output(RUN_BRAKE, OFF)
                time.sleep(0.1)
                GPIO.output(START_STOP, OFF)
            
            self.rotation_interrupted = True
            self._emergency_stop_requested = False
            self._reset_state_after_stop()
            
            print(f"✓ 緊急停止完了")
        except Exception as e:
            print(f"❌ 緊急停止中エラー: {e}")
    
    def normal_stop(self):
        """正常停止"""
        with self.lock:
            if not self._is_running:
                return
            
            try:
                print("⏹ 正常停止")
                if GPIO_AVAILABLE:
                    GPIO.output(RUN_BRAKE, OFF)
                    time.sleep(0.1)
                    GPIO.output(START_STOP, OFF)
                
                self.rotation_interrupted = False
                self._reset_state_after_stop()
                
                self.phase_count += 1
                self.total_rotations += 1
                
            except Exception as e:
                print(f"❌ 正常停止中エラー: {e}")

    def _reset_state_after_stop(self):
        """停止後の状態リセット"""
        self._is_running = False
        self.direction = "STOP"
        self.rotation_start_time = None
    
    def get_next_rotation_direction(self):
        """次の回転方向を決定"""
        with self.lock:
            if self.rotation_phase == "ccw_cycle":
                if self.phase_count >= 10:
                    self.rotation_phase = "cw_cycle"
                    self.phase_count = 0
                    self.current_direction_cw = True
                else:
                    self.current_direction_cw = False
            elif self.rotation_phase == "cw_cycle":
                if self.phase_count >= 10:
                    self.rotation_phase = "ccw_cycle"
                    self.phase_count = 0
                    self.current_direction_cw = False
                else:
                    self.current_direction_cw = True
            
            self.elapsed_time = 0.0
            self.rotation_interrupted = False


def initialize_vosk():
    """Vosk初期化"""
    global vosk_model
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, 'vosk-model-small-ja-0.22')
        
        if not os.path.exists(model_path):
            print(f"⚠️ Voskモデルが見つかりません")
            return
        
        print(f"Voskモデルを初期化中...")
        vosk_model = Model(model_path)
        print(f"✓ Vosk小モデルを初期化しました")
        
    except Exception as e:
        print(f"✗ Voskモデルの初期化に失敗: {e}")

def initialize_vad():
    """VAD初期化"""
    global vad_model
    
    try:
        print("Silero VADモデルを初期化中...")
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        print("✓ Silero VADモデルを初期化しました")
        
    except Exception as e:
        print(f"⚠️ Silero VADの初期化に失敗: {e}")

def detect_answer_keyword(text: str) -> Optional[bool]:
    """キーワード検出"""
    text_lower = text.lower().replace(' ', '')
    
    maru_keywords = ['まる', 'マル', '丸', '○', 'まぁる', 'まーる', 'maru', 'ある']
    for keyword in maru_keywords:
        if keyword in text_lower or keyword in text:
            return True
    
    batsu_keywords = ['ばつ', 'バツ', 'ペケ', '×', 'ばっ', 'batsu', '月']
    for keyword in batsu_keywords:
        if keyword in text_lower or keyword in text:
            return False
    
    return None

class FastKeywordSpotter:
    """高速キーワードスポッティング"""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.sample_rate = SAMPLE_RATE
        self.audio_buffer = deque(maxlen=int(SAMPLE_RATE * 10))
        self.speech_buffer = []
        self.is_speech = False
        self.silence_duration = 0
        
        self.vad_threshold = 0.4
        self.speech_pad_ms = 200
        self.min_speech_duration = 0.25
        self.max_speech_duration = 3.0
        self.vad_chunk_size = 512
        self.pending_samples = np.array([], dtype=np.float32)
        
        if vosk_model is not None:
            self.recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            self.recognizer.SetWords(True)
            self.recognizer.SetPartialWords(True)
        else:
            self.recognizer = None
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> Optional[dict]:
        """音声チャンク処理"""
        if vad_model is None or self.recognizer is None:
            return None
        
        self.audio_buffer.extend(audio_data)
        
        combined_data = np.concatenate([self.pending_samples, audio_data])
        num_full_chunks = len(combined_data) // self.vad_chunk_size
        
        for i in range(num_full_chunks):
            start_idx = i * self.vad_chunk_size
            end_idx = start_idx + self.vad_chunk_size
            chunk = combined_data[start_idx:end_idx]
            
            result = self._process_vad_chunk(chunk)
            if result:
                return result
        
        remaining_start = num_full_chunks * self.vad_chunk_size
        self.pending_samples = combined_data[remaining_start:]
        
        return None
    
    def _process_vad_chunk(self, chunk: np.ndarray) -> Optional[dict]:
        """VADチャンク処理"""
        audio_tensor = torch.from_numpy(chunk).float()
        
        try:
            speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
        except Exception as e:
            return None
        
        is_speech_now = speech_prob > self.vad_threshold
        
        if is_speech_now and not self.is_speech:
            self.is_speech = True
            self.silence_duration = 0
            
            pad_samples = int(SAMPLE_RATE * self.speech_pad_ms / 1000)
            pad_data = list(self.audio_buffer)[-pad_samples:] if len(self.audio_buffer) >= pad_samples else list(self.audio_buffer)
            self.speech_buffer = pad_data + list(chunk)
            
            if self.recognizer:
                self.recognizer.Reset()
        
        elif is_speech_now and self.is_speech:
            self.speech_buffer.extend(chunk)
            self.silence_duration = 0
            
            audio_int16 = (np.array(chunk) * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            if self.recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                
                if text:
                    answer = detect_answer_keyword(text)
                    if answer is not None:
                        self.is_speech = False
                        self.speech_buffer = []
                        
                        return {
                            'type': 'speech_result',
                            'text': text,
                            'answer': answer,
                            'is_final': True
                        }
            else:
                partial_result = json.loads(self.recognizer.PartialResult())
                partial_text = partial_result.get('partial', '').strip()
                
                if partial_text:
                    answer = detect_answer_keyword(partial_text)
                    if answer is not None:
                        self.is_speech = False
                        self.speech_buffer = []
                        
                        final_result = json.loads(self.recognizer.FinalResult())
                        
                        return {
                            'type': 'speech_result',
                            'text': partial_text,
                            'answer': answer,
                            'is_final': True
                        }
            
            duration = len(self.speech_buffer) / SAMPLE_RATE
            if duration > self.max_speech_duration:
                return self._finalize_recognition()
        
        elif not is_speech_now and self.is_speech:
            self.speech_buffer.extend(chunk)
            self.silence_duration += len(chunk) / SAMPLE_RATE
            
            if self.silence_duration > 0.3:
                duration = len(self.speech_buffer) / SAMPLE_RATE
                
                if duration >= self.min_speech_duration:
                    return self._finalize_recognition()
                else:
                    self.is_speech = False
                    self.speech_buffer = []
        
        return None
    
    def _finalize_recognition(self) -> Optional[dict]:
        """認識確定"""
        if not self.speech_buffer or self.recognizer is None:
            self.is_speech = False
            self.speech_buffer = []
            return None
        
        try:
            result = json.loads(self.recognizer.FinalResult())
            text = result.get('text', '').strip()
            
            if text:
                answer = detect_answer_keyword(text)
                
                self.is_speech = False
                self.speech_buffer = []
                
                return {
                    'type': 'speech_result',
                    'text': text,
                    'answer': answer,
                    'is_final': True
                }
        
        except Exception as e:
            print(f"❌ 認識エラー: {e}")
        
        self.is_speech = False
        self.speech_buffer = []
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ライフサイクル管理"""
    initialize_detector()
    initialize_vad()
    initialize_vosk()
    initialize_motor()
    yield
    cleanup_motor()
    print("サーバーをシャットダウンしています...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def initialize_motor():
    """モーター初期化"""
    global motor_controller
    
    if GPIO_AVAILABLE:
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(START_STOP, GPIO.OUT)
            GPIO.setup(RUN_BRAKE, GPIO.OUT)
            GPIO.setup(CW_CCW, GPIO.OUT)
            GPIO.setup(INT_VR_EXT, GPIO.OUT)
            print("✓ GPIO初期化完了")
        except Exception as e:
            print(f"❌ GPIO初期化エラー: {e}")
    
    motor_controller = MotorController()
    motor_controller.initialize()

def cleanup_motor():
    """モータークリーンアップ"""
    global motor_controller
    
    if motor_controller:
        motor_controller.normal_stop()
    
    if GPIO_AVAILABLE:
        try:
            GPIO.cleanup()
            print("✓ GPIO クリーンアップ完了")
        except:
            pass

def initialize_detector():
    """物体検出初期化"""
    global detector
    
    try:
        from nanodet import NanoDetONNX
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, 'model', 'nanodet_m_320.onnx')
        
        if not os.path.exists(model_path):
            print(f"⚠️ 物体検出モデルが見つかりません")
            return
        
        detector = NanoDetONNX(
            model_path=model_path,
            input_shape=320,
            class_score_th=0.5,
            nms_th=0.6,
        )
        print(f"✓ 物体検出モデルを初期化しました")
    except Exception as e:
        print(f"⚠️ 物体検出の初期化をスキップ: {e}")

async def broadcast_message(message: dict):
    """全クライアントにメッセージ送信"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            disconnected.add(connection)
    
    active_connections.difference_update(disconnected)

async def run_detection():
    """物体検出ループ（モーター制御統合版）"""
    global detection_running, motor_state
    
    if detector is None or motor_controller is None:
        return
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("カメラを開けませんでした")
        return
    
    print("物体検出を開始しました")
    person_class_id = 0
    stable_detection_count = 0
    STABLE_THRESHOLD = 3
    
    try:
        while detection_running:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue
            
            # 物体検出
            bboxes, scores, class_ids = detector.inference(frame)
            person_count = sum(1 for i, cid in enumerate(class_ids) if cid == person_class_id and scores[i] >= 0.6)
            person_detected = person_count > 0
            
            with motor_state_lock:
                # モーター制御ロジック
                if motor_state["is_stopped_for_answer"]:
                    # 回答待ち状態: 何もしない
                    pass
                
                elif person_detected:
                    stable_detection_count += 1
                    
                    if stable_detection_count >= STABLE_THRESHOLD:
                        # 人を安定検出 → モーター停止
                        if motor_controller.is_running:
                            print(f"\n👤 人検出確定! モーター停止 👤\n")
                            motor_controller.request_emergency_stop()
                        
                        # スナップショット取得（人の部分を切り取り）
                        if len(bboxes) > 0:
                            # 最初の検出領域を使用
                            x, y, w, h = bboxes[0].astype(int)
                            
                            # 余裕を持たせてクロップ
                            margin = 20
                            x1 = max(0, x - margin)
                            y1 = max(0, y - margin)
                            x2 = min(frame.shape[1], x + w + margin)
                            y2 = min(frame.shape[0], y + h + margin)
                            
                            person_crop = frame[y1:y2, x1:x2]
                            
                            # Base64エンコード
                            _, buffer = cv2.imencode('.jpg', person_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            img_base64 = base64.b64encode(buffer).decode('utf-8')
                            
                            motor_state["snapshot_image"] = img_base64
                            motor_state["detection_timestamp"] = time.time()
                        
                        # クライアントに通知
                        await broadcast_message({
                            "type": "person_selected",
                            "count": person_count,
                            "snapshot": motor_state["snapshot_image"],
                            "timestamp": time.time()
                        })
                        
                        # 回答待ち状態に移行
                        motor_state["is_stopped_for_answer"] = True
                        stable_detection_count = 0
                
                else:
                    stable_detection_count = 0
                    
                    # モーターが停止している場合は再開
                    if not motor_controller.is_running and not motor_state["is_stopped_for_answer"]:
                        # 半回転完了チェック
                        if motor_controller.rotation_interrupted:
                            # 中断からの復帰
                            pass
                        else:
                            # 次の回転を開始
                            motor_controller.get_next_rotation_direction()
                            time.sleep(0.5)
                            motor_controller.start_slow_rotation()
                            motor_state["is_running"] = True
                
                # モーターが回転中の処理
                if motor_controller.is_running:
                    if motor_controller.check_rotation_complete():
                        motor_controller.normal_stop()
                        motor_state["is_running"] = False
                    else:
                        motor_controller.execute_one_step()
            
            await asyncio.sleep(0.1)
    
    finally:
        cap.release()
        print("物体検出を停止しました")

@app.get("/")
async def root():
    return {
        "message": "クイズゲーム用モーター制御統合サーバー",
        "websocket_endpoints": {
            "detection": "/ws/detection",
            "speech": "/ws/speech"
        },
        "motor_ready": motor_controller is not None,
        "vosk_ready": vosk_model is not None,
        "vad_ready": vad_model is not None,
        "detector_ready": detector is not None
    }

@app.get("/status")
async def status():
    with motor_state_lock:
        return {
            "detection_running": detection_running,
            "active_connections": len(active_connections),
            "motor_running": motor_state["is_running"],
            "motor_stopped_for_answer": motor_state["is_stopped_for_answer"],
            "vosk_model_loaded": vosk_model is not None,
            "vad_model_loaded": vad_model is not None,
            "detector_loaded": detector is not None
        }

@app.post("/motor/resume")
async def resume_motor():
    """モーター再開API（解説終了後に呼ばれる）"""
    global motor_state
    
    with motor_state_lock:
        if motor_state["is_stopped_for_answer"]:
            print("🔄 モーター再開リクエスト受信")
            motor_state["is_stopped_for_answer"] = False
            motor_state["snapshot_image"] = None
            motor_state["detection_timestamp"] = None
            
            # 少し待機してから再開（同じ人の再検出を避ける）
            await asyncio.sleep(3.0)
            
            if not motor_controller.is_running:
                motor_controller.get_next_rotation_direction()
                motor_controller.start_slow_rotation()
                motor_state["is_running"] = True
                print("✓ モーター再開完了")
            
            return {"status": "resumed"}
        else:
            return {"status": "not_stopped"}

@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    
    if detector is not None and motor_controller is not None and not detection_running:
        detection_running = True
        
        # モーター初回起動
        await asyncio.sleep(2)
        motor_controller.start_slow_rotation()
        with motor_state_lock:
            motor_state["is_running"] = True
        
        asyncio.create_task(run_detection())
    
    try:
        while True:
            data = await websocket.receive()
            
            if "text" in data:
                message = json.loads(data["text"])
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        
        if len(active_connections) == 0:
            detection_running = False
    except Exception as e:
        print(f"物体検出WebSocketエラー: {e}")
        active_connections.discard(websocket)

@app.websocket("/ws/speech")
async def websocket_speech(websocket: WebSocket):
    await websocket.accept()
    connection_id = str(id(websocket))
    
    spotter = FastKeywordSpotter(connection_id)
    audio_buffers[connection_id] = spotter
    
    try:
        while True:
            try:
                message = await websocket.receive()
                
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        if data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                    except json.JSONDecodeError:
                        pass
                
                elif "bytes" in message:
                    audio_bytes = message["bytes"]
                    
                    if vosk_model is not None and vad_model is not None:
                        try:
                            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                            audio_float = audio_np.astype(np.float32) / 32768.0
                            
                            result = spotter.process_audio_chunk(audio_float)
                            
                            if result:
                                await websocket.send_json(result)
                        
                        except Exception as e:
                            print(f"❌ 音声処理エラー: {e}")
                
                elif "type" in message and message["type"] == "websocket.disconnect":
                    break
            
            except Exception as e:
                if "disconnect" in str(e).lower():
                    break
                else:
                    print(f"❌ メッセージ受信エラー: {e}")
                    break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"音声認識WebSocketエラー: {e}")
    finally:
        if connection_id in audio_buffers:
            del audio_buffers[connection_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
  
