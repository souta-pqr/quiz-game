#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vosk音声認識を統合したバックエンドサーバー
"""

import asyncio
import cv2
import json
import time
import os
import wave
import numpy as np
from typing import Set
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from vosk import Model, KaldiRecognizer
import struct

# グローバル変数
active_connections: Set[WebSocket] = set()
detector = None
detection_running = False
last_person_detected_time = None
person_detected_notified = False
stable_detection_count = 0
STABLE_DETECTION_THRESHOLD = 5

# Vosk関連
vosk_model = None
SAMPLE_RATE = 16000  # Voskは16kHzを推奨

# WebSocket接続ごとにKaldiRecognizerを保持
recognizers = {}

def get_or_create_recognizer(connection_id: str) -> KaldiRecognizer:
    """接続IDに対応するKaldiRecognizerを取得または作成"""
    if connection_id not in recognizers:
        if vosk_model is None:
            return None
        recognizers[connection_id] = KaldiRecognizer(vosk_model, SAMPLE_RATE)
        recognizers[connection_id].SetWords(True)
        print(f"✓ 新しいKaldiRecognizerを作成: {connection_id}")
    return recognizers[connection_id]

def cleanup_recognizer(connection_id: str):
    """接続終了時にKaldiRecognizerをクリーンアップ"""
    if connection_id in recognizers:
        del recognizers[connection_id]
        print(f"✓ KaldiRecognizerをクリーンアップ: {connection_id}")

def process_audio_with_vosk(audio_data: bytes, connection_id: str) -> dict:
    """
    Voskを使って音声データを処理
    
    Args:
        audio_data: 16kHz, 16-bit PCM 形式の音声データ
        connection_id: WebSocket接続ID
    
    Returns:
        認識結果の辞書
    """
    if vosk_model is None:
        return {"error": "Vosk model not initialized"}
    
    try:
        rec = get_or_create_recognizer(connection_id)
        if rec is None:
            return {"error": "Failed to create recognizer"}
        
        # 音声データを処理
        if rec.AcceptWaveform(audio_data):
            result = json.loads(rec.Result())
            if "text" in result and result["text"]:
                print(f"✓ 完全認識: '{result['text']}'")
                return result
        
        # 部分認識結果を取得
        result = json.loads(rec.PartialResult())
        if "partial" in result and result["partial"]:
            print(f"⋯ 部分認識: '{result['partial']}'")
        
        return result
    except Exception as e:
        print(f"❌ 音声認識エラー: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    initialize_detector()
    initialize_vosk_model()
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

def initialize_vosk_model():
    """Vosk音声認識モデルを初期化"""
    global vosk_model
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # モデルの候補パス
    model_paths = [
        os.path.join(script_dir, 'model', 'vosk-model-small-ja-0.22'),
        os.path.join(script_dir, 'vosk-model-small-ja-0.22'),
        '/opt/vosk/model/vosk-model-small-ja-0.22',
    ]
    
    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            break
    
    if model_path is None:
        print("⚠️  Voskモデルが見つかりません")
        print("以下のコマンドでダウンロードしてください:")
        print("cd backend")
        print("wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip")
        print("unzip vosk-model-small-ja-0.22.zip")
        print("または、model/ディレクトリに配置してください")
        return
    
    try:
        vosk_model = Model(model_path)
        print(f"✓ Vosk音声認識モデルを初期化しました: {model_path}")
    except Exception as e:
        print(f"✗ Voskモデルの初期化に失敗: {e}")

def initialize_detector():
    """物体検出モデルを初期化"""
    global detector
    
    try:
        from nanodet import NanoDetONNX
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, 'model', 'nanodet_m_320.onnx')
        
        if not os.path.exists(model_path):
            print(f"⚠️  物体検出モデルが見つかりません: {model_path}")
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
        print(f"⚠️  物体検出の初期化をスキップ: {e}")

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
        "message": "Object Detection + Vosk Speech Recognition Server",
        "vosk_ready": vosk_model is not None,
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
        "vosk_model_loaded": vosk_model is not None,
        "detector_loaded": detector is not None
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """メインのWebSocketエンドポイント"""
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    connection_id = str(id(websocket))
    print(f"WebSocket接続が確立されました。接続ID: {connection_id}、アクティブ接続数: {len(active_connections)}")
    
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
            
            elif "bytes" in data:
                # 音声データを受信
                audio_data = data["bytes"]
                
                # デバッグ: データサイズを定期的に表示（10回に1回）
                if not hasattr(websocket, '_chunk_count'):
                    websocket._chunk_count = 0
                websocket._chunk_count += 1
                
                if websocket._chunk_count % 10 == 0:
                    print(f"📦 音声データ受信 (接続ID: {connection_id}): {len(audio_data)} バイト")
                
                if vosk_model is not None:
                    result = process_audio_with_vosk(audio_data, connection_id)
                    
                    # エラーがあれば送信
                    if "error" in result:
                        await websocket.send_json({
                            "type": "speech_error",
                            "error": result["error"]
                        })
                        continue
                    
                    # テキストが認識された場合（完全認識）
                    if "text" in result and result["text"]:
                        text = result["text"]
                        
                        # 「まる」「ばつ」を検出
                        answer = None
                        if "まる" in text or "マル" in text or "丸" in text:
                            answer = True
                            print("✓ 回答検出: まる")
                        elif "ばつ" in text or "バツ" in text or "ペケ" in text or "ばっ" in text:
                            answer = False
                            print("✓ 回答検出: ばつ")
                        
                        await websocket.send_json({
                            "type": "speech_result",
                            "text": text,
                            "answer": answer,
                            "is_final": True
                        })
                    
                    # 部分認識結果がある場合
                    elif "partial" in result and result["partial"]:
                        partial_text = result["partial"]
                        
                        await websocket.send_json({
                            "type": "speech_result",
                            "text": partial_text,
                            "answer": None,
                            "is_final": False
                        })
                else:
                    if websocket._chunk_count == 1:
                        print("⚠️  Voskモデルが初期化されていません")
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        cleanup_recognizer(connection_id)
        print(f"WebSocket接続が切断されました。接続ID: {connection_id}、アクティブ接続数: {len(active_connections)}")
        
        if len(active_connections) == 0:
            detection_running = False
    except Exception as e:
        print(f"WebSocketエラー: {e}")
        import traceback
        traceback.print_exc()
        active_connections.discard(websocket)
        cleanup_recognizer(connection_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    