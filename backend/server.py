#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import cv2
import json
import time
import os
from typing import Set
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from nanodet import NanoDetONNX

# グローバル変数
active_connections: Set[WebSocket] = set()
detector = None
detection_running = False
last_person_detected_time = None
person_detected_notified = False
stable_detection_count = 0  # 安定した検出回数をカウント
STABLE_DETECTION_THRESHOLD = 5  # 5フレーム連続で検出されたら確定

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_detector()
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
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, 'model', 'nanodet_m_320.onnx')
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")
    
    input_shape = 320
    score_th = 0.5  # 信頼度スコアを0.35から0.5に上げる（誤検知を減らす）
    nms_th = 0.6
    
    detector = NanoDetONNX(
        model_path=model_path,
        input_shape=input_shape,
        class_score_th=score_th,
        nms_th=nms_th,
    )
    print(f"物体検出モデルを初期化しました: {model_path}")
    print(f"信頼度スコア閾値: {score_th}")

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
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("カメラを開けませんでした")
        return
    
    print("物体検出を開始しました")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    coco_classes_path = os.path.join(script_dir, 'coco_classes.txt')
    
    with open(coco_classes_path, 'rt') as f:
        coco_classes = f.read().rstrip('\n').split('\n')
    
    person_class_id = 0
    
    try:
        while detection_running:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue
            
            # 推論実施
            bboxes, scores, class_ids = detector.inference(frame)
            
            # Personクラスの検出をチェック（信頼度スコアも確認）
            person_detected = False
            person_count = 0
            high_confidence_persons = []
            
            for i, class_id in enumerate(class_ids):
                if class_id == person_class_id:
                    # 信頼度スコアが0.6以上のもののみカウント
                    if scores[i] >= 0.6:
                        person_count += 1
                        high_confidence_persons.append({
                            'score': scores[i],
                            'bbox': bboxes[i]
                        })
            
            if person_count > 0:
                person_detected = True
                print(f"検出: {person_count}人 (スコア: {[f'{p['score']:.2f}' for p in high_confidence_persons]})")
            
            current_time = time.time()
            
            if person_detected:
                stable_detection_count += 1
                
                # 安定して検出されたら初回通知
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
                    
                    # 3秒経過後に音声再生トリガー
                    elif not person_detected_notified and (current_time - last_person_detected_time) >= 3.0:
                        person_detected_notified = True
                        print("✓ 3秒経過 - 音声再生をトリガーします")
                        
                        await broadcast_message({
                            "type": "play_audio",
                            "message": "Person detected for 3 seconds",
                            "count": person_count
                        })
            else:
                # 人が検出されなくなったらリセット
                if stable_detection_count > 0:
                    stable_detection_count = 0
                    
                if last_person_detected_time is not None:
                    print("人が検出されなくなりました")
                    last_person_detected_time = None
                    person_detected_notified = False
            
            # フレームレートを制限
            await asyncio.sleep(0.15)  # 0.1秒から0.15秒に変更（CPU負荷軽減）
    
    finally:
        cap.release()
        print("物体検出を停止しました")

@app.get("/")
async def root():
    return {"message": "Object Detection Server is running"}

@app.get("/status")
async def status():
    """サーバーのステータスを返す"""
    return {
        "detection_running": detection_running,
        "active_connections": len(active_connections),
        "person_detected": last_person_detected_time is not None,
        "stable_detection_count": stable_detection_count
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocketエンドポイント"""
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    print(f"WebSocket接続が確立されました。アクティブ接続数: {len(active_connections)}")
    
    if not detection_running:
        detection_running = True
        asyncio.create_task(run_detection())
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"WebSocket接続が切断されました。アクティブ接続数: {len(active_connections)}")
        
        if len(active_connections) == 0:
            detection_running = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
