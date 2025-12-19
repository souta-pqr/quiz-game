#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
統合サーバー
"""

import asyncio
import json
import numpy as np
from typing import Set
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# 各モジュールのインポート
from modules.gpio_controller import GPIOWrapper, GPIO_AVAILABLE, GPIO_LIBRARY
from modules.motor_controller import MotorController
from modules.object_detector import (
    initialize_detector, 
    run_detection, 
    motor_state,
    motor_state_lock,
    set_detection_running,
    get_detection_running,
    is_detector_ready
)

# voice_recognitionモジュール全体をインポート
from modules import voice_recognition

# グローバル変数
active_connections: Set[WebSocket] = set()
motor_controller = None
audio_buffers = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ライフサイクル管理"""
    print("サーバー起動処理開始...")
    
    initialize_detector()
    voice_recognition.initialize_vad()
    voice_recognition.initialize_vosk()
    initialize_motor()
    
    print("サーバー起動処理完了")
    
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
        GPIOWrapper.setup_pins()
    
    motor_controller = MotorController()
    
    try:
        motor_controller.initialize()
    except Exception as e:
        print(f"モーター初期化エラー: {e}")


def cleanup_motor():
    """モータークリーンアップ"""
    global motor_controller
    
    if motor_controller:
        try:
            motor_controller.normal_stop()
        except:
            pass
    
    GPIOWrapper.cleanup()


async def broadcast_message(message: dict):
    """全クライアントにメッセージ送信（スレッドセーフ）"""
    # イテレーション中のセット変更を避けるため、コピーを作成
    connections_snapshot = list(active_connections.copy())
    disconnected = set()
    
    for connection in connections_snapshot:
        try:
            await connection.send_json(message)
        except Exception as e:
            disconnected.add(connection)
    
    # 切断された接続を削除
    if disconnected:
        active_connections.difference_update(disconnected)


@app.get("/")
async def root():
    return {
        "message": "クイズゲーム用モーター制御統合サーバー",
        "version": "2.0",
        "websocket_endpoints": {
            "detection": "/ws/detection",
            "speech": "/ws/speech"
        },
        "gpio_library": GPIO_LIBRARY if GPIO_AVAILABLE else "dummy",
        "motor_ready": motor_controller is not None and motor_controller.is_initialized,
        "vosk_ready": voice_recognition.vosk_model is not None,
        "vad_ready": voice_recognition.vad_model is not None,
        "detector_ready": is_detector_ready(),
        "features": [
            "位置追跡（-90° 〜 +90°）",
            "回答者再選択（ランダム回転）",
            "ケーブル巻き込み防止",
            "モジュール分割によるコード整理"
        ]
    }


@app.get("/status")
async def status():
    with motor_state_lock:
        motor_angle = motor_controller.current_angle if motor_controller else 0.0
        return {
            "active_connections": len(active_connections),
            "motor_running": motor_state["is_running"],
            "motor_stopped_for_answer": motor_state["is_stopped_for_answer"],
            "motor_angle": f"{motor_angle:.1f}°",
            "vosk_model_loaded": voice_recognition.vosk_model is not None,
            "vad_model_loaded": voice_recognition.vad_model is not None,
            "detector_loaded": is_detector_ready(),
            "motor_initialized": motor_controller is not None and motor_controller.is_initialized,
            "gpio_library": GPIO_LIBRARY if GPIO_AVAILABLE else "dummy"
        }


@app.post("/motor/resume")
async def resume_motor():
    """モーター再開API（解説終了後に呼ばれる）"""
    global motor_state
    
    try:
        with motor_state_lock:
            if motor_state["is_stopped_for_answer"]:
                # モーター処理中を通知
                try:
                    await broadcast_message({
                        "type": "motor_processing",
                        "message": "次の回答者を選んでいます...",
                        "status": "started"
                    })
                except Exception as e:
                    print(f"ブロードキャストエラー（開始）: {e}")
                
                await asyncio.sleep(0.5)
                
                # 交互ランダム回転で回答者を再選択
                if motor_controller and motor_controller.is_initialized:
                    try:
                        motor_controller.perform_random_rotation_for_reselection()
                    except Exception as e:
                        print(f"モーター回転エラー: {e}")
                
                # 待機（同じ人の再検出を避ける）
                await asyncio.sleep(3.0)
                
                # 回答待ち状態を解除
                motor_state["is_stopped_for_answer"] = False
                motor_state["snapshot_image"] = None
                motor_state["detection_timestamp"] = None
                
                # 処理完了を通知
                try:
                    await broadcast_message({
                        "type": "motor_processing",
                        "message": "処理完了",
                        "status": "completed"
                    })
                except Exception as e:
                    print(f"ブロードキャストエラー（完了）: {e}")
                
                await asyncio.sleep(0.5)
                
                # 通常の回転を再開
                if not motor_controller.is_running and motor_controller.is_initialized:
                    motor_controller.get_next_rotation_direction()
                    motor_controller.start_slow_rotation()
                    motor_state["is_running"] = True
                
                return {"status": "resumed", "message": "回答者再選択完了"}
            else:
                return {"status": "not_stopped", "message": "回答待ち状態ではありません"}
    
    except Exception as e:
        print(f"モーター再開エラー: {e}")
        return {"status": "error", "message": str(e)}


@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    """物体検出WebSocketエンドポイント"""
    await websocket.accept()
    active_connections.add(websocket)
    
    if is_detector_ready() and motor_controller is not None and motor_controller.is_initialized:
        if not get_detection_running():
            set_detection_running(True)
            
            # モーター初回起動
            await asyncio.sleep(2)
            motor_controller.start_slow_rotation()
            with motor_state_lock:
                motor_state["is_running"] = True
            
            asyncio.create_task(run_detection(motor_controller, broadcast_message))
    
    try:
        while True:
            try:
                data = await websocket.receive()
                
                if "text" in data:
                    message = json.loads(data["text"])
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break
            except Exception as e:
                # 切断関連のエラーは正常終了として扱う
                if "disconnect" in str(e).lower() or "Cannot call" in str(e):
                    break
                print(f"物体検出メッセージ処理エラー: {e}")
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        if "disconnect" not in str(e).lower():
            print(f"物体検出WebSocketエラー: {e}")
    finally:
        # 確実に接続を削除
        active_connections.discard(websocket)
        
        if len(active_connections) == 0:
            set_detection_running(False)


@app.websocket("/ws/speech")
async def websocket_speech(websocket: WebSocket):
    """音声認識WebSocketエンドポイント"""
    await websocket.accept()
    connection_id = str(id(websocket))
    
    spotter = voice_recognition.FastKeywordSpotter(connection_id)
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
                    
                    if voice_recognition.vosk_model is not None and voice_recognition.vad_model is not None:
                        try:
                            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                            audio_float = audio_np.astype(np.float32) / 32768.0
                            
                            result = spotter.process_audio_chunk(audio_float)
                            
                            if result:
                                await websocket.send_json(result)
                        
                        except Exception as e:
                            pass
                
                elif "type" in message and message["type"] == "websocket.disconnect":
                    break
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                # 切断関連のエラーは正常終了として扱う
                if "disconnect" in str(e).lower() or "Cannot call" in str(e):
                    break
                # その他のエラーも終了
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # エラーは静かに処理
        pass
    finally:
        # 確実にバッファを削除
        if connection_id in audio_buffers:
            del audio_buffers[connection_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
