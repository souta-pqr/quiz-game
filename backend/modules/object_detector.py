#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
物体検出モジュール
NanoDetによる人物検出
"""

import os
import cv2
import time
import base64
import asyncio
import threading
from typing import Optional, Tuple


# グローバル変数
detector = None
detection_running = False
motor_state = {
    "is_running": False,
    "is_stopped_for_answer": False,
    "snapshot_image": None,
    "detection_timestamp": None
}
motor_state_lock = threading.RLock()


def set_detection_running(value: bool):
    """detection_runningの値を設定"""
    global detection_running
    detection_running = value


def get_detection_running() -> bool:
    """detection_runningの値を取得"""
    global detection_running
    return detection_running


def get_detector():
    """detectorの値を取得"""
    global detector
    return detector


def is_detector_ready() -> bool:
    """detectorが初期化されているか確認"""
    global detector
    return detector is not None


def initialize_detector():
    """物体検出初期化"""
    global detector
    
    try:
        from nanodet import NanoDetONNX
        
        # modules/ディレクトリの親ディレクトリ（backend/）を基準にする
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


async def run_detection(motor_controller_instance, broadcast_callback):
    """物体検出ループ（モーター制御統合版）
    
    Args:
        motor_controller_instance: モーターコントローラーインスタンス
        broadcast_callback: メッセージブロードキャスト用コールバック
    """
    global detection_running, motor_state
    
    motor_controller = motor_controller_instance
    
    print(f"🔍 run_detection() 呼び出し:")
    print(f"   detector: {detector is not None}")
    print(f"   motor_controller: {motor_controller is not None}")
    print(f"   motor_controller.is_initialized: {motor_controller.is_initialized if motor_controller else 'N/A'}")
    print(f"   detection_running: {detection_running}")
    
    if detector is None or motor_controller is None or not motor_controller.is_initialized:
        print("⚠️ 検出またはモーターが初期化されていません")
        return
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        return
    
    print("✓ 物体検出を開始しました")
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
                        await broadcast_callback({
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
        print("✓ 物体検出を停止しました")
