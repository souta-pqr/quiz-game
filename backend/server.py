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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    initialize_detector()
    yield
    # シャットダウン時の処理
    print("サーバーをシャットダウンしています...")

app = FastAPI(lifespan=lifespan)

# CORS設定
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
    import os
    
    # スクリプトのディレクトリを基準にパスを解決
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, 'model', 'nanodet_m_320.onnx')
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"モデルファイルが見つかりません: {model_path}")
    
    input_shape = 320
    score_th = 0.35
    nms_th = 0.6
    
    detector = NanoDetONNX(
        model_path=model_path,
        input_shape=input_shape,
        class_score_th=score_th,
        nms_th=nms_th,
    )
    print(f"物体検出モデルを初期化しました: {model_path}")

async def broadcast_message(message: dict):
    """全ての接続されたクライアントにメッセージを送信"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            print(f"送信エラー: {e}")
            disconnected.add(connection)
    
    # 切断されたコネクションを削除
    active_connections.difference_update(disconnected)

async def run_detection():
    """物体検出を継続的に実行"""
    global detection_running, last_person_detected_time, person_detected_notified
    import os
    
    # カメラ初期化
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("カメラを開けませんでした")
        return
    
    print("物体検出を開始しました")
    
    # COCOクラスリスト読み込み
    script_dir = os.path.dirname(os.path.abspath(__file__))
    coco_classes_path = os.path.join(script_dir, 'coco_classes.txt')
    
    with open(coco_classes_path, 'rt') as f:
        coco_classes = f.read().rstrip('\n').split('\n')
    
    person_class_id = 0  # COCOデータセットでPersonは0
    
    try:
        while detection_running:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue
            
            # 推論実施
            bboxes, scores, class_ids = detector.inference(frame)
            
            # Personクラスの検出をチェック
            person_detected = False
            person_count = 0
            
            for class_id in class_ids:
                if class_id == person_class_id:
                    person_detected = True
                    person_count += 1
            
            current_time = time.time()
            
            if person_detected:
                if last_person_detected_time is None:
                    # 初回検出
                    last_person_detected_time = current_time
                    person_detected_notified = False
                    print(f"人を検出しました（{person_count}人）")
                    
                    # クライアントに通知
                    await broadcast_message({
                        "type": "person_detected",
                        "count": person_count,
                        "timestamp": current_time
                    })
                
                # 3秒経過後に音声再生トリガー
                elif not person_detected_notified and (current_time - last_person_detected_time) >= 3.0:
                    person_detected_notified = True
                    print("3秒経過 - 音声再生をトリガーします")
                    
                    await broadcast_message({
                        "type": "play_audio",
                        "message": "Person detected for 3 seconds"
                    })
            else:
                # 人が検出されなくなったらリセット
                if last_person_detected_time is not None:
                    print("人が検出されなくなりました")
                last_person_detected_time = None
                person_detected_notified = False
            
            # フレームレートを制限（CPU負荷軽減）
            await asyncio.sleep(0.1)
    
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
        "person_detected": last_person_detected_time is not None
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocketエンドポイント"""
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    print(f"WebSocket接続が確立されました。アクティブ接続数: {len(active_connections)}")
    
    # 物体検出がまだ開始されていない場合は開始
    if not detection_running:
        detection_running = True
        asyncio.create_task(run_detection())
    
    try:
        while True:
            # クライアントからのメッセージを受信（keep-alive用）
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"WebSocket接続が切断されました。アクティブ接続数: {len(active_connections)}")
        
        # 全ての接続が切断されたら検出を停止
        if len(active_connections) == 0:
            detection_running = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
