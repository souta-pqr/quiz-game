#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
超軽量キーワードスポッティングサーバー
Vosk小モデル + VADで「まる」「ばつ」のみを高速検出
"""

import asyncio
import cv2
import json
import time
import os
import numpy as np
import torch
from typing import Set, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from vosk import Model, KaldiRecognizer

# グローバル変数
active_connections: Set[WebSocket] = set()
detector = None
detection_running = False
last_person_detected_time = None
person_detected_notified = False
stable_detection_count = 0
STABLE_DETECTION_THRESHOLD = 5

# Vosk + VAD関連
vosk_model = None
vad_model = None
SAMPLE_RATE = 16000

# WebSocket接続ごとに音声バッファを保持
audio_buffers = {}

def initialize_vosk():
    """Voskの小モデルを初期化"""
    global vosk_model
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, 'vosk-model-small-ja-0.22')
        
        if not os.path.exists(model_path):
            print(f"⚠️ Voskモデルが見つかりません: {model_path}")
            print("以下のコマンドでダウンロードしてください:")
            print("  cd backend")
            print("  wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip")
            print("  unzip vosk-model-small-ja-0.22.zip")
            return
        
        print(f"Voskモデルを初期化中: {model_path}")
        vosk_model = Model(model_path)
        print(f"✓ Vosk小モデルを初期化しました（約50MB、軽量版）")
        
    except Exception as e:
        print(f"✗ Voskモデルの初期化に失敗: {e}")
        import traceback
        traceback.print_exc()

def initialize_vad():
    """Silero VADモデルを初期化"""
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
    """テキストから「まる」「ばつ」を高速検出
    
    Args:
        text: 認識されたテキスト
        
    Returns:
        True: まる, False: ばつ, None: どちらでもない
    """
    text_lower = text.lower().replace(' ', '')
    
    # 「まる」系のキーワード（より柔軟に）
    maru_keywords = [
        'まる', 'マル', '丸', '○', 
        'まぁる', 'まーる', 'まるまる',
        'maru', 'まるっ', 'まるい', 'ある'
    ]
    for keyword in maru_keywords:
        if keyword in text_lower or keyword in text:
            return True
    
    # 「ばつ」系のキーワード（より柔軟に）
    batsu_keywords = [
        'ばつ', 'バツ', 'ペケ', '×', 
        'ばっ', 'ばっつ', 'ばつばつ',
        'batsu', 'ばつっ', '月'
    ]
    for keyword in batsu_keywords:
        if keyword in text_lower or keyword in text:
            return False
    
    return None

class FastKeywordSpotter:
    """超高速キーワードスポッティング
    
    VAD + Vosk小モデルで「まる」「ばつ」のみを検出
    レイテンシを最小化するための最適化：
    - 部分認識結果も活用
    - バッファサイズを最小化
    - キーワード検出後、即座に応答
    """
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.sample_rate = SAMPLE_RATE
        self.audio_buffer = deque(maxlen=int(SAMPLE_RATE * 10))
        self.speech_buffer = []
        self.is_speech = False
        self.silence_duration = 0
        
        # VAD設定を高速化のために調整
        self.vad_threshold = 0.4  # 少し低めで反応を速く
        self.speech_pad_ms = 200  # パディングを短く
        self.min_speech_duration = 0.25  # 最小音声を短く
        self.max_speech_duration = 3.0   # 最大音声を短く
        self.vad_chunk_size = 512
        self.pending_samples = np.array([], dtype=np.float32)
        
        # Vosk認識器を初期化
        if vosk_model is not None:
            self.recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            self.recognizer.SetWords(True)
            # 部分認識結果も取得するように設定
            self.recognizer.SetPartialWords(True)
        else:
            self.recognizer = None
        
        print(f"✓ FastKeywordSpotter初期化: {connection_id}")
        print(f"  VAD閾値: {self.vad_threshold} (低め=高感度)")
        print(f"  最小音声長: {self.min_speech_duration}秒")
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> Optional[dict]:
        """音声チャンクを処理"""
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
        """VADチャンクを処理"""
        audio_tensor = torch.from_numpy(chunk).float()
        
        try:
            speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
        except Exception as e:
            print(f"❌ VADエラー: {e}")
            return None
        
        is_speech_now = speech_prob > self.vad_threshold
        
        # 音声開始
        if is_speech_now and not self.is_speech:
            self.is_speech = True
            self.silence_duration = 0
            
            pad_samples = int(SAMPLE_RATE * self.speech_pad_ms / 1000)
            pad_data = list(self.audio_buffer)[-pad_samples:] if len(self.audio_buffer) >= pad_samples else list(self.audio_buffer)
            self.speech_buffer = pad_data + list(chunk)
            
            if self.recognizer:
                self.recognizer.Reset()
            
            print(f"🎤 音声検出 (信頼度: {speech_prob:.2f})")
        
        # 音声継続中 - リアルタイムで認識
        elif is_speech_now and self.is_speech:
            self.speech_buffer.extend(chunk)
            self.silence_duration = 0
            
            # 認識器にデータを送る
            audio_int16 = (np.array(chunk) * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # 部分認識結果をチェック
            if self.recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                
                if text:
                    answer = detect_answer_keyword(text)
                    if answer is not None:
                        print(f"✓ キーワード即座検出: '{text}'")
                        self.is_speech = False
                        self.speech_buffer = []
                        
                        return {
                            'type': 'speech_result',
                            'text': text,
                            'answer': answer,
                            'is_final': True
                        }
            else:
                # 部分認識結果もチェック（さらに高速化）
                partial_result = json.loads(self.recognizer.PartialResult())
                partial_text = partial_result.get('partial', '').strip()
                
                if partial_text:
                    answer = detect_answer_keyword(partial_text)
                    if answer is not None:
                        # 部分結果でもキーワードを検出したら即座に応答
                        print(f"✓ キーワード部分検出: '{partial_text}'")
                        self.is_speech = False
                        self.speech_buffer = []
                        
                        # 最終結果として送る
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
        
        # 音声終了
        elif not is_speech_now and self.is_speech:
            self.speech_buffer.extend(chunk)
            self.silence_duration += len(chunk) / SAMPLE_RATE
            
            if self.silence_duration > 0.3:  # 300ms無音で終了（短め）
                duration = len(self.speech_buffer) / SAMPLE_RATE
                
                if duration >= self.min_speech_duration:
                    return self._finalize_recognition()
                else:
                    self.is_speech = False
                    self.speech_buffer = []
        
        return None
    
    def _finalize_recognition(self) -> Optional[dict]:
        """認識を確定"""
        if not self.speech_buffer or self.recognizer is None:
            self.is_speech = False
            self.speech_buffer = []
            return None
        
        try:
            # 最終結果を取得
            result = json.loads(self.recognizer.FinalResult())
            text = result.get('text', '').strip()
            
            if text:
                print(f"✓ 最終認識: '{text}'")
                
                answer = detect_answer_keyword(text)
                
                if answer is True:
                    print("  → ○ まる")
                elif answer is False:
                    print("  → × ばつ")
                
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
    """アプリケーションのライフサイクル管理"""
    initialize_detector()
    initialize_vad()
    initialize_vosk()
    yield
    print("サーバーをシャットダウンしています...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def initialize_detector():
    """物体検出モデルを初期化"""
    global detector
    
    try:
        from nanodet import NanoDetONNX
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, 'model', 'nanodet_m_320.onnx')
        
        if not os.path.exists(model_path):
            print(f"⚠️ 物体検出モデルが見つかりません: {model_path}")
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
    """全ての接続されたクライアントにメッセージを送信"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            disconnected.add(connection)
    
    active_connections.difference_update(disconnected)

async def run_detection():
    """物体検出を継続的に実行"""
    global detection_running, last_person_detected_time, person_detected_notified, stable_detection_count
    
    if detector is None:
        return
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("カメラを開けませんでした")
        return
    
    print("物体検出を開始しました")
    person_class_id = 0
    
    try:
        while detection_running:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue
            
            bboxes, scores, class_ids = detector.inference(frame)
            
            person_count = sum(1 for i, cid in enumerate(class_ids) if cid == person_class_id and scores[i] >= 0.6)
            person_detected = person_count > 0
            
            current_time = time.time()
            
            if person_detected:
                stable_detection_count += 1
                
                if stable_detection_count >= STABLE_DETECTION_THRESHOLD:
                    if last_person_detected_time is None:
                        last_person_detected_time = current_time
                        person_detected_notified = False
                        print(f"✓ 人を安定検出（{person_count}人）")
                        
                        await broadcast_message({
                            "type": "person_detected",
                            "count": person_count,
                            "timestamp": current_time
                        })
                    
                    elif not person_detected_notified and (current_time - last_person_detected_time) >= 3.0:
                        person_detected_notified = True
                        print("✓ 3秒経過 - 音声再生をトリガー")
                        
                        await broadcast_message({
                            "type": "play_audio",
                            "message": "Person detected for 3 seconds",
                            "count": person_count
                        })
            else:
                if stable_detection_count > 0:
                    stable_detection_count = 0
                    
                if last_person_detected_time is not None:
                    print("人が検出されなくなりました")
                    last_person_detected_time = None
                    person_detected_notified = False
            
            await asyncio.sleep(0.15)
    
    finally:
        cap.release()
        print("物体検出を停止しました")

@app.get("/")
async def root():
    return {
        "message": "Ultra-Fast Keyword Spotting Server (まる/ばつ専用)",
        "websocket_endpoints": {
            "detection": "/ws/detection",
            "speech": "/ws/speech"
        },
        "vosk_ready": vosk_model is not None,
        "vad_ready": vad_model is not None,
        "detector_ready": detector is not None,
        "model_size": "~50MB",
        "optimized_for": "Raspberry Pi 5"
    }

@app.get("/status")
async def status():
    return {
        "detection_running": detection_running,
        "active_connections": len(active_connections),
        "person_detected": last_person_detected_time is not None,
        "vosk_model_loaded": vosk_model is not None,
        "vad_model_loaded": vad_model is not None,
        "detector_loaded": detector is not None
    }

@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    connection_id = str(id(websocket))
    print(f"🔌 物体検出WebSocket接続: {connection_id}")
    
    if detector is not None and not detection_running:
        detection_running = True
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
        print(f"🔌 物体検出WebSocket切断: {connection_id}")
        
        if len(active_connections) == 0:
            detection_running = False
    except Exception as e:
        print(f"物体検出WebSocketエラー: {e}")
        active_connections.discard(websocket)

@app.websocket("/ws/speech")
async def websocket_speech(websocket: WebSocket):
    await websocket.accept()
    connection_id = str(id(websocket))
    print(f"🎤 音声認識WebSocket接続: {connection_id}")
    
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
                                print(f"📤 送信: {result.get('text', '')}")
                                await websocket.send_json(result)
                        
                        except Exception as e:
                            print(f"❌ 音声処理エラー: {e}")
                            await websocket.send_json({
                                "type": "speech_error",
                                "error": str(e)
                            })
                
                elif "type" in message and message["type"] == "websocket.disconnect":
                    break
            
            except Exception as e:
                if "disconnect" in str(e).lower():
                    break
                else:
                    print(f"❌ メッセージ受信エラー: {e}")
                    break
    
    except WebSocketDisconnect:
        print(f"🎤 音声認識WebSocket切断: {connection_id}")
    except Exception as e:
        print(f"音声認識WebSocketエラー: {e}")
    finally:
        if connection_id in audio_buffers:
            del audio_buffers[connection_id]
        print(f"🧹 クリーンアップ完了: {connection_id}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
