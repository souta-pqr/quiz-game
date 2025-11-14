#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Whisper + Silero VADを統合したバックエンドサーバー
"""

import asyncio
import cv2
import json
import time
import os
import wave
import numpy as np
import torch
import whisper
from typing import Set, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
import io

# グローバル変数
active_connections: Set[WebSocket] = set()
detector = None
detection_running = False
last_person_detected_time = None
person_detected_notified = False
stable_detection_count = 0
STABLE_DETECTION_THRESHOLD = 5

# Whisper + VAD関連
whisper_model = None
vad_model = None
SAMPLE_RATE = 16000

# WebSocket接続ごとに音声バッファを保持
audio_buffers = {}
vad_states = {}

def initialize_whisper():
    """Whisperモデルを初期化"""
    global whisper_model
    
    try:
        # 小さいモデルから始める（精度とスピードのバランス）
        model_name = "base"  # tiny, base, small, medium, large から選択
        print(f"Whisperモデルをダウンロード・初期化中: {model_name}")
        whisper_model = whisper.load_model(model_name)
        print(f"✓ Whisperモデル '{model_name}' を初期化しました")
        
        # GPUが利用可能か確認
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"✓ 使用デバイス: {device}")
        
    except Exception as e:
        print(f"✗ Whisperモデルの初期化に失敗: {e}")
        print("pip install openai-whisper を実行してください")

def initialize_vad():
    """Silero VADモデルを初期化"""
    global vad_model
    
    try:
        print("Silero VADモデルを初期化中...")
        # Silero VADモデルをダウンロード
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        print("✓ Silero VADモデルを初期化しました")
        
    except Exception as e:
        print(f"⚠️ Silero VADの初期化に失敗: {e}")
        print("VADなしで動作します（音声認識精度が低下する可能性があります）")

class AudioProcessor:
    """音声処理クラス（VAD + Whisper）"""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.sample_rate = SAMPLE_RATE
        self.audio_buffer = deque(maxlen=int(SAMPLE_RATE * 10))  # 最大10秒分のバッファ
        self.speech_buffer = []
        self.is_speech = False
        self.speech_start_time = None
        self.silence_duration = 0
        self.vad_threshold = 0.000001  # 0.5 → 0.1に大幅に下げる
        self.speech_pad_ms = 300  # 音声前後のパディング（ミリ秒）
        self.min_speech_duration = 0.3  # 最小音声長（秒）
        self.max_speech_duration = 10.0  # 最大音声長（秒）
        
        print(f"✓ AudioProcessor初期化: {connection_id}")
        print(f"  VAD閾値: {self.vad_threshold} (低感度モード)")
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> Optional[dict]:
        """
        音声チャンクを処理（VAD + Whisper）
        
        Args:
            audio_data: 16kHz, float32の音声データ
            
        Returns:
            認識結果のdict、またはNone
        """
        if vad_model is None or whisper_model is None:
            return None
        
        # 音声データの振幅チェック（最初の10回のみ）
        if not hasattr(self, '_amplitude_check_count'):
            self._amplitude_check_count = 0
        
        if self._amplitude_check_count < 10:
            max_amp = np.abs(audio_data).max()
            mean_amp = np.abs(audio_data).mean()
            print(f"🎚️ 音声振幅 #{self._amplitude_check_count + 1}: max={max_amp:.4f}, mean={mean_amp:.4f}")
            self._amplitude_check_count += 1
        
        # バッファに追加
        self.audio_buffer.extend(audio_data)
        
        # VAD処理
        chunk_size = int(SAMPLE_RATE * 0.512)  # 512msチャンク
        
        if len(audio_data) < chunk_size:
            # データが不足している場合はパディング
            padded = np.zeros(chunk_size, dtype=np.float32)
            padded[:len(audio_data)] = audio_data
            audio_chunk = padded
        else:
            audio_chunk = audio_data[:chunk_size]
        
        # PyTorchテンソルに変換
        audio_tensor = torch.from_numpy(audio_chunk).float()
        
        # VADで音声区間を検出
        try:
            speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
        except Exception as e:
            print(f"VADエラー: {e}")
            return None
        
        is_speech_now = speech_prob > self.vad_threshold
        
        # デバッグ: VADの結果を定期的にログ
        if not hasattr(self, '_vad_log_count'):
            self._vad_log_count = 0
        self._vad_log_count += 1
        
        # 最初の50回は毎回、その後は50回ごと
        if self._vad_log_count <= 50 or self._vad_log_count % 50 == 0:
            print(f"🔊 VAD確率: {speech_prob:.3f} (閾値: {self.vad_threshold}) [カウント: {self._vad_log_count}]")
        
        # 音声区間の開始
        if is_speech_now and not self.is_speech:
            self.is_speech = True
            self.speech_start_time = time.time()
            self.silence_duration = 0
            
            # パディング分のデータを追加
            pad_samples = int(SAMPLE_RATE * self.speech_pad_ms / 1000)
            pad_data = list(self.audio_buffer)[-pad_samples:] if len(self.audio_buffer) >= pad_samples else list(self.audio_buffer)
            self.speech_buffer = pad_data + list(audio_data)
            
            print(f"🎤 音声開始検出 (信頼度: {speech_prob:.2f})")
        
        # 音声区間の継続
        elif is_speech_now and self.is_speech:
            self.speech_buffer.extend(audio_data)
            self.silence_duration = 0
            
            # 最大音声長チェック
            duration = len(self.speech_buffer) / SAMPLE_RATE
            if duration > self.max_speech_duration:
                print(f"⏱️ 最大音声長到達 ({duration:.1f}秒)")
                return self._process_speech_buffer()
        
        # 音声区間の終了候補
        elif not is_speech_now and self.is_speech:
            self.speech_buffer.extend(audio_data)
            self.silence_duration += len(audio_data) / SAMPLE_RATE
            
            # 無音が一定時間続いたら音声区間終了
            if self.silence_duration > 0.5:  # 500ms無音
                duration = len(self.speech_buffer) / SAMPLE_RATE
                
                if duration >= self.min_speech_duration:
                    print(f"🔚 音声終了検出 (長さ: {duration:.1f}秒)")
                    return self._process_speech_buffer()
                else:
                    print(f"⏭️ 音声が短すぎるためスキップ ({duration:.1f}秒)")
                    self.is_speech = False
                    self.speech_buffer = []
        
        return None
    
    def _process_speech_buffer(self) -> Optional[dict]:
        """
        音声バッファをWhisperで認識
        
        Returns:
            認識結果のdict
        """
        if not self.speech_buffer or whisper_model is None:
            self.is_speech = False
            self.speech_buffer = []
            return None
        
        try:
            # numpy配列に変換
            audio_array = np.array(self.speech_buffer, dtype=np.float32)
            
            # 正規化（-1.0 ~ 1.0の範囲に）
            max_val = np.abs(audio_array).max()
            if max_val > 0:
                audio_array = audio_array / max_val
            
            print(f"🔄 Whisper認識開始... (長さ: {len(audio_array)/SAMPLE_RATE:.1f}秒)")
            
            # Whisperで認識
            result = whisper_model.transcribe(
                audio_array,
                language='ja',
                task='transcribe',
                fp16=False,
                verbose=False
            )
            
            text = result['text'].strip()
            
            if text:
                print(f"✓ 認識結果: '{text}'")
                
                # 回答判定
                answer = None
                if any(word in text for word in ['まる', 'マル', '丸', '○']):
                    answer = True
                    print("  → ○ まる として認識")
                elif any(word in text for word in ['ばつ', 'バツ', 'ペケ', '×', 'ばっ']):
                    answer = False
                    print("  → × ばつ として認識")
                
                # バッファをクリア
                self.is_speech = False
                self.speech_buffer = []
                
                return {
                    'type': 'speech_result',
                    'text': text,
                    'answer': answer,
                    'is_final': True
                }
            else:
                print("⚠️ 認識結果が空です")
        
        except Exception as e:
            print(f"❌ Whisper認識エラー: {e}")
            import traceback
            traceback.print_exc()
        
        # バッファをクリア
        self.is_speech = False
        self.speech_buffer = []
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    initialize_detector()
    initialize_vad()
    initialize_whisper()
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
        
        input_shape = 320
        score_th = 0.5
        nms_th = 0.6
        
        detector = NanoDetONNX(
            model_path=model_path,
            input_shape=input_shape,
            class_score_th=score_th,
            nms_th=nms_th,
        )
        print(f"✓ 物体検出モデルを初期化しました: {model_path}")
    except Exception as e:
        print(f"⚠️ 物体検出の初期化をスキップ: {e}")

async def broadcast_message(message: dict):
    """全ての接続されたクライアントにメッセージを送信"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            print(f"送信エラー: {e}")
            disconnected.add(connection)
    
    active_connections.difference_update(disconnected)

async def run_detection():
    """物体検出を継続的に実行"""
    global detection_running, last_person_detected_time, person_detected_notified, stable_detection_count
    
    if detector is None:
        print("物体検出モデルが初期化されていません")
        return
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("カメラを開けませんでした")
        return
    
    print("物体検出を開始しました")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    coco_classes_path = os.path.join(script_dir, 'coco_classes.txt')
    
    coco_classes = []
    if os.path.exists(coco_classes_path):
        with open(coco_classes_path, 'rt') as f:
            coco_classes = f.read().rstrip('\n').split('\n')
    
    person_class_id = 0
    
    try:
        while detection_running:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue
            
            bboxes, scores, class_ids = detector.inference(frame)
            
            person_detected = False
            person_count = 0
            high_confidence_persons = []
            
            for i, class_id in enumerate(class_ids):
                if class_id == person_class_id:
                    if scores[i] >= 0.6:
                        person_count += 1
                        high_confidence_persons.append({
                            'score': scores[i],
                            'bbox': bboxes[i]
                        })
            
            if person_count > 0:
                person_detected = True
                scores_str = ', '.join([f"{p['score']:.2f}" for p in high_confidence_persons])
                print(f"検出: {person_count}人 (スコア: [{scores_str}])")
            
            current_time = time.time()
            
            if person_detected:
                stable_detection_count += 1
                
                if stable_detection_count >= STABLE_DETECTION_THRESHOLD:
                    if last_person_detected_time is None:
                        last_person_detected_time = current_time
                        person_detected_notified = False
                        print(f"✓ 人を安定検出しました（{person_count}人）")
                        
                        await broadcast_message({
                            "type": "person_detected",
                            "count": person_count,
                            "timestamp": current_time
                        })
                    
                    elif not person_detected_notified and (current_time - last_person_detected_time) >= 3.0:
                        person_detected_notified = True
                        print("✓ 3秒経過 - 音声再生をトリガーします")
                        
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
        "message": "Object Detection + Whisper + Silero VAD Server",
        "websocket_endpoints": {
            "detection": "/ws/detection",
            "speech": "/ws/speech"
        },
        "whisper_ready": whisper_model is not None,
        "vad_ready": vad_model is not None,
        "detector_ready": detector is not None
    }

@app.get("/status")
async def status():
    """サーバーのステータスを返す"""
    return {
        "detection_running": detection_running,
        "active_connections": len(active_connections),
        "person_detected": last_person_detected_time is not None,
        "stable_detection_count": stable_detection_count,
        "whisper_model_loaded": whisper_model is not None,
        "vad_model_loaded": vad_model is not None,
        "detector_loaded": detector is not None
    }

@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    """物体検出用WebSocketエンドポイント"""
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    connection_id = str(id(websocket))
    print(f"🔌 物体検出WebSocket接続: {connection_id}")
    
    # 物体検出を開始
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
    """音声認識用WebSocketエンドポイント"""
    await websocket.accept()
    connection_id = str(id(websocket))
    print(f"🎤 音声認識WebSocket接続: {connection_id}")
    
    # AudioProcessorを作成
    audio_processor = AudioProcessor(connection_id)
    audio_buffers[connection_id] = audio_processor
    
    try:
        chunk_count = 0
        loop_count = 0
        
        print(f"🔄 メッセージ受信ループ開始")
        
        while True:
            loop_count += 1
            
            # 最初の10回だけループカウントをログ
            if loop_count <= 10:
                print(f"🔁 ループ#{loop_count}: メッセージ待機中...")
            
            try:
                # テキストまたはバイナリデータを受信
                message = await websocket.receive()
                
                # 最初の10回はメッセージタイプをログ
                if loop_count <= 10:
                    print(f"📨 ループ#{loop_count}: メッセージ受信 - keys={list(message.keys())}")
                
                # デバッグ: 最初のメッセージの内容を詳細にログ
                if chunk_count == 0:
                    print(f"🔍 最初のメッセージ: type={type(message)}, keys={message.keys()}")
                
                # テキストメッセージ（JSON）
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                        
                        if data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                            print(f"🏓 Pong送信")
                    except json.JSONDecodeError:
                        print(f"⚠️ JSON解析エラー: {message['text'][:100]}")
                
                # バイナリメッセージ（音声データ）
                elif "bytes" in message:
                    audio_bytes = message["bytes"]
                    chunk_count += 1
                    
                    if chunk_count == 1:
                        print(f"✓ 初回音声データ受信: {len(audio_bytes)} バイト")
                    elif chunk_count <= 5 or chunk_count % 20 == 0:
                        print(f"📦 音声データ受信: {len(audio_bytes)} バイト (チャンク#{chunk_count})")
                    
                    if whisper_model is not None and vad_model is not None:
                        try:
                            # bytesをnumpy配列に変換（16-bit PCM）
                            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                            
                            # float32に変換して正規化（-1.0 ~ 1.0）
                            audio_float = audio_np.astype(np.float32) / 32768.0
                            
                            # 最初の5回だけ配列情報をログ
                            if chunk_count <= 5:
                                print(f"🎵 音声データ変換: {len(audio_np)} サンプル -> {len(audio_float)} float32")
                            
                            # VAD + Whisper処理
                            result = audio_processor.process_audio_chunk(audio_float)
                            
                            if result:
                                print(f"📤 認識結果を送信: {result.get('text', '')}")
                                await websocket.send_json(result)
                        
                        except Exception as e:
                            print(f"❌ 音声処理エラー: {e}")
                            import traceback
                            traceback.print_exc()
                            
                            await websocket.send_json({
                                "type": "speech_error",
                                "error": str(e)
                            })
                    else:
                        if chunk_count == 1:
                            print("⚠️ Whisper/VADモデルが初期化されていません")
                
                # WebSocket切断メッセージ
                elif "type" in message and message["type"] == "websocket.disconnect":
                    print(f"🔌 クライアントから切断要求: {connection_id}")
                    break
                
                # その他
                else:
                    if chunk_count < 5:  # 最初の5回だけログ
                        print(f"⚠️ 不明なメッセージ形式: {message.keys()}")
                        if "type" in message:
                            print(f"   メッセージタイプ: {message.get('type')}")
            
            except Exception as e:
                # receive()内のエラー
                error_msg = str(e)
                if "disconnect" in error_msg.lower():
                    print(f"🔌 WebSocket切断検出: {connection_id}")
                    break
                else:
                    print(f"❌ メッセージ受信エラー (ループ#{loop_count}): {e}")
                    import traceback
                    traceback.print_exc()
                    break
        
        print(f"🔚 メッセージ受信ループ終了 (ループ回数: {loop_count}, チャンク数: {chunk_count})")
    
    except WebSocketDisconnect:
        print(f"🎤 音声認識WebSocket切断: {connection_id}")
    except Exception as e:
        print(f"音声認識WebSocketエラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if connection_id in audio_buffers:
            del audio_buffers[connection_id]
        print(f"🧹 AudioProcessorクリーンアップ完了: {connection_id}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    