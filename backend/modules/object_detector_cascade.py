#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
物体検出モジュール（OpenCV Cascade版・デバッグ強化）
カスケード分類器による顔検出
"""

import os
import cv2
import time
import base64
import asyncio
import threading
import numpy as np
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

# 検出設定（緩和）
STABLE_DETECTION_COUNT = 2  # 3→2に変更（より早く検出）
FRAME_WIDTH = 640
FRAME_HEIGHT = 480


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


class CascadePersonDetector:
    """OpenCVカスケード分類器による顔検出クラス"""
    
    def __init__(self, cascade_path=None):
        print("🔍 カスケード分類器読み込み中...")
        if cascade_path is None:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_alt.xml'
        
        self.cascade = cv2.CascadeClassifier(cascade_path)
        
        if self.cascade.empty():
            raise FileNotFoundError(f"カスケード分類器の読み込みに失敗: {cascade_path}")
        
        self.stable_count = 0
        self.detection_count = 0
        self.last_log_time = 0
        print("✓ カスケード分類器読み込み完了")
        print(f"  検出パラメータ: minNeighbors=2, minSize=(60,60)")
    
    def detect_person(self, frame):
        """顔検出
        
        Returns:
            person_detected: bool - 人が検出されたか
            person_count: int - 検出された人数
            stable_detection: bool - 安定検出されたか
            detections: list - 検出領域のリスト [(x, y, w, h), ...]
        """
        try:
            self.detection_count += 1
            
            # グレースケール変換とヒストグラム均等化
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            
            # 顔検出（パラメータを緩和）
            detections = self.cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=2,      # 3→2に変更（感度UP）
                minSize=(60, 60),    # 90→60に変更（小さい顔も検出）
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            person_count = len(detections)
            
            if person_count > 0:
                self.stable_count += 1
            else:
                self.stable_count = 0
            
            # 安定検出の判定
            stable_detection = self.stable_count >= STABLE_DETECTION_COUNT
            person_detected = person_count > 0
            
            # 100フレームごとまたは検出時にログ出力
            current_time = time.time()
            if self.detection_count % 100 == 0 or person_detected:
                if current_time - self.last_log_time > 2.0:  # 2秒に1回
                    print(f"🔍 検出状況 (フレーム{self.detection_count}): "
                          f"検出={person_count}人, 連続={self.stable_count}, "
                          f"安定={stable_detection}")
                    self.last_log_time = current_time
            
            return person_detected, person_count, stable_detection, detections
            
        except Exception as e:
            print(f"❌ 検出処理エラー: {e}")
            return False, 0, False, []


def initialize_detector():
    """物体検出初期化（Cascade版）"""
    global detector
    
    try:
        detector = CascadePersonDetector()
        print(f"✓ カスケード分類器による物体検出を初期化しました")
    except Exception as e:
        print(f"⚠️ 物体検出の初期化に失敗: {e}")


async def run_detection(motor_controller_instance, broadcast_callback):
    """物体検出ループ（モーター制御統合版・Cascade対応）
    
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
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        return
    
    print("✓ 物体検出を開始しました")
    print(f"  安定検出閾値: {STABLE_DETECTION_COUNT}フレーム連続")
    print(f"  フレームサイズ: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    
    frame_count = 0
    last_status_log = time.time()
    
    try:
        while detection_running:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.1)
                continue
            
            frame_count += 1
            
            # 10秒ごとに状態ログ
            current_time = time.time()
            if current_time - last_status_log > 10.0:
                print(f"📹 カメラ動作中: {frame_count}フレーム処理済み")
                last_status_log = current_time
            
            # 顔検出（Cascade版）
            person_detected, person_count, stable_detection, detections = detector.detect_person(frame)
            
            with motor_state_lock:
                # モーター制御ロジック
                if motor_state["is_stopped_for_answer"]:
                    # 回答待ち状態: 何もしない
                    pass
                
                elif stable_detection:
                    # 人を安定検出 → モーター停止
                    if motor_controller.is_running:
                        print(f"\n{'='*60}")
                        print(f"👤 人検出確定! ({person_count}人) モーター停止")
                        print(f"   検出領域数: {len(detections)}")
                        if len(detections) > 0:
                            x, y, w, h = detections[0]
                            print(f"   最大領域: x={x}, y={y}, w={w}, h={h}")
                        print(f"{'='*60}\n")
                        motor_controller.request_emergency_stop()
                    
                    # スナップショット取得（最初の検出領域を使用）
                    if len(detections) > 0:
                        x, y, w, h = detections[0].astype(int)
                        
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
                        
                        print(f"📷 スナップショット取得完了: {len(img_base64)}バイト")
                    
                    # クライアントに通知
                    await broadcast_callback({
                        "type": "person_selected",
                        "count": person_count,
                        "snapshot": motor_state["snapshot_image"],
                        "timestamp": time.time()
                    })
                    
                    print(f"📤 クライアントに通知送信完了")
                    
                    # 回答待ち状態に移行
                    motor_state["is_stopped_for_answer"] = True
                
                else:
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
        print(f"✓ 物体検出を停止しました (総フレーム数: {frame_count})")
        
