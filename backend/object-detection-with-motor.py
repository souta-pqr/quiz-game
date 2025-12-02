#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import cv2
import numpy as np
from nanodet import NanoDetONNX
import threading

# ===================================
# GPIO設定
# ===================================
START_STOP = 24
RUN_BRAKE = 12
CW_CCW = 14
INT_VR_EXT = 1

# 信号レベル
ON = GPIO.LOW
OFF = GPIO.HIGH

# ===================================
# モーター設定
# ===================================
ROTATION_TIME = 3.0

# ===================================
# 物体検出設定
# ===================================
DETECTION_THRESHOLD = 0.25  # 閾値を下げて検出しやすく
STABLE_DETECTION_COUNT = 2
PERSON_CLASS_ID = 0

class MotorController:
    """BLHモーター制御クラス"""
    
    def __init__(self, rotation_time=ROTATION_TIME):
        self.is_initialized = False
        self.is_running = False
        self.direction = "STOP"
        self.rotation_time = rotation_time
        self.current_direction_cw = True
        self.rotation_start_time = None
        self.elapsed_time_before_stop = 0.0
        self.rotation_interrupted = False
        self.lock = threading.Lock()
    
    def initialize(self):
        print("🔧 モーター初期化中...")
        GPIO.output(START_STOP, OFF)
        GPIO.output(RUN_BRAKE, OFF)
        GPIO.output(CW_CCW, OFF)
        GPIO.output(INT_VR_EXT, ON)
        time.sleep(0.5)
        self.is_initialized = True
        self.is_running = False
        print("✓ モーター初期化完了")
    
    def start_cw(self):
        with self.lock:
            if not self.is_initialized:
                return False
            print("▶ CW起動")
            GPIO.output(CW_CCW, ON)
            time.sleep(0.1)
            GPIO.output(START_STOP, ON)
            time.sleep(0.5)
            GPIO.output(RUN_BRAKE, ON)
            self.is_running = True
            self.direction = "CW"
            self.rotation_start_time = time.time()
            return True
    
    def start_ccw(self):
        with self.lock:
            if not self.is_initialized:
                return False
            print("▶ CCW起動")
            GPIO.output(CW_CCW, OFF)
            time.sleep(0.1)
            GPIO.output(START_STOP, ON)
            time.sleep(0.5)
            GPIO.output(RUN_BRAKE, ON)
            self.is_running = True
            self.direction = "CCW"
            self.rotation_start_time = time.time()
            return True
    
    def start_next_rotation(self):
        if self.rotation_interrupted:
            print(f"🔄 再開（残り{self.get_remaining_time():.1f}s）")
            self.rotation_interrupted = False
            if self.current_direction_cw:
                self.start_cw()
            else:
                self.start_ccw()
            with self.lock:
                self.rotation_start_time -= self.elapsed_time_before_stop
        else:
            if self.current_direction_cw:
                self.start_cw()
            else:
                self.start_ccw()
    
    def switch_direction(self):
        with self.lock:
            self.current_direction_cw = not self.current_direction_cw
            self.elapsed_time_before_stop = 0.0
            self.rotation_interrupted = False
        print(f"🔄 次: {'CW' if self.current_direction_cw else 'CCW'}")
    
    def check_rotation_complete(self):
        with self.lock:
            if not self.is_running or self.rotation_start_time is None:
                return False
            elapsed = time.time() - self.rotation_start_time
            return elapsed >= self.rotation_time
    
    def get_remaining_time(self):
        with self.lock:
            if not self.is_running or self.rotation_start_time is None:
                return max(0.0, self.rotation_time - self.elapsed_time_before_stop)
            elapsed = time.time() - self.rotation_start_time
            return max(0.0, self.rotation_time - elapsed)
    
    def emergency_stop(self):
        with self.lock:
            if not self.is_running:
                return
            print("🛑 緊急停止!")
            if self.rotation_start_time is not None:
                self.elapsed_time_before_stop = time.time() - self.rotation_start_time
                self.rotation_interrupted = True
            GPIO.output(RUN_BRAKE, OFF)
            GPIO.output(START_STOP, OFF)
            self.is_running = False
            self.direction = "STOP"
            self.rotation_start_time = None
    
    def normal_stop(self):
        with self.lock:
            if not self.is_running:
                return
            print("⏹ 停止")
            GPIO.output(RUN_BRAKE, OFF)
            time.sleep(0.3)
            GPIO.output(START_STOP, OFF)
            self.is_running = False
            self.direction = "STOP"
            self.rotation_start_time = None
            self.elapsed_time_before_stop = 0.0
            self.rotation_interrupted = False

class DebugPersonDetector:
    """デバッグ機能付き物体検出クラス"""
    
    def __init__(self, model_path=None):
        print("🔍 物体検出モデル読み込み中...")
        
        if model_path is None:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            possible_paths = [
                os.path.join(script_dir, 'model', 'nanodet_m_320.onnx'),
                os.path.join(script_dir, 'backend', 'model', 'nanodet_m_320.onnx'),
                '/home/fujielab-raspi5/work/quiz-game/backend/model/nanodet_m_320.onnx',
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    print(f"✓ モデル発見: {model_path}")
                    break
            
            if model_path is None:
                raise FileNotFoundError("NanoDetモデルファイルが見つかりません")
        
        # 標準サイズで初期化（検出精度優先）
        self.detector = NanoDetONNX(
            model_path=model_path,
            input_shape=320,  # 標準サイズ
            class_score_th=DETECTION_THRESHOLD,
            nms_th=0.6,
        )
        self.stable_count = 0
        self.detection_count = 0
        self.last_detection_time = time.time()
        print("✓ 検出モデル読み込み完了（320x320）")
        print(f"  検出閾値: {DETECTION_THRESHOLD}")
        print(f"  安定検出カウント: {STABLE_DETECTION_COUNT}")
    
    def detect_person(self, frame):
        """デバッグ情報付き検出"""
        self.detection_count += 1
        
        # 標準サイズで検出
        bboxes, scores, class_ids = self.detector.inference(frame)
        
        # 全検出結果を表示（デバッグ用）
        if len(class_ids) > 0:
            print(f"\n[検出 #{self.detection_count}]")
            for i, (bbox, score, class_id) in enumerate(zip(bboxes, scores, class_ids)):
                # COCOクラス名
                class_names = ['person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat']
                class_name = class_names[class_id] if class_id < len(class_names) else f'class_{class_id}'
                print(f"  {i+1}. {class_name} (ID:{class_id}): 信頼度 {score:.3f}")
        
        # 人クラスのみをフィルタリング
        person_detections = [
            (i, score) for i, (cid, score) in enumerate(zip(class_ids, scores))
            if cid == PERSON_CLASS_ID and score >= DETECTION_THRESHOLD
        ]
        
        person_count = len(person_detections)
        person_detected = person_count > 0
        
        if person_detected:
            print(f"  ✓ 人を検出: {person_count}人")
            for idx, (i, score) in enumerate(person_detections):
                print(f"    人#{idx+1}: 信頼度 {score:.3f}")
            self.stable_count += 1
        else:
            if len(class_ids) > 0:
                print(f"  ✗ 人は検出されず（他のオブジェクトのみ）")
            self.stable_count = 0
        
        stable_detection = self.stable_count >= STABLE_DETECTION_COUNT
        
        if stable_detection:
            print(f"  🎯 安定検出! ({self.stable_count}/{STABLE_DETECTION_COUNT})")
        
        return person_detected, person_count, stable_detection

class DetectionThread(threading.Thread):
    """検出専用スレッド（デバッグ版）"""
    
    def __init__(self, cap, detector, motor, stop_event):
        super().__init__(daemon=True)
        self.cap = cap
        self.detector = detector
        self.motor = motor
        self.stop_event = stop_event
        self.person_detected_flag = False
        self.stable_detection_flag = False
        self.frame_count = 0
    
    def run(self):
        print("🔍 検出スレッド起動")
        
        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                print("⚠ フレーム取得失敗")
                time.sleep(0.1)
                continue
            
            self.frame_count += 1
            
            # フレーム情報を定期的に表示
            if self.frame_count % 30 == 0:
                print(f"\n[フレーム #{self.frame_count}] 形状: {frame.shape}")
            
            # 検出実行
            person_detected, person_count, stable_detection = self.detector.detect_person(frame)
            
            self.person_detected_flag = person_detected
            self.stable_detection_flag = stable_detection
            
            # 安定検出したら即座にモーター停止
            if stable_detection and self.motor.is_running:
                print(f"\n👤👤👤 人検出確定! ({person_count}人) - モーター緊急停止 👤👤👤\n")
                self.motor.emergency_stop()
            
            time.sleep(0.05)  # 検出頻度（20fps相当）
        
        print("🔍 検出スレッド終了")

def main():
    """メイン処理"""
    
    # GPIO初期化
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(START_STOP, GPIO.OUT)
    GPIO.setup(RUN_BRAKE, GPIO.OUT)
    GPIO.setup(CW_CCW, GPIO.OUT)
    GPIO.setup(INT_VR_EXT, GPIO.OUT)
    
    # モーター制御初期化
    motor = MotorController(rotation_time=ROTATION_TIME)
    motor.initialize()
    
    # 物体検出初期化
    person_detector = DebugPersonDetector()
    
    # カメラ初期化（標準解像度）
    print("📷 カメラ初期化中...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        return
    
    print("✓ カメラ初期化完了（640x480）")
    print()
    print("=" * 60)
    print("デバッグ版モーター制御システム")
    print("=" * 60)
    print("機能:")
    print("  - 検出結果を詳細に表示")
    print("  - 全オブジェクトの検出情報を出力")
    print("  - 人検出時に詳細な信頼度を表示")
    print("=" * 60)
    print()
    
    # 検出スレッド起動
    stop_event = threading.Event()
    detection_thread = DetectionThread(cap, person_detector, motor, stop_event)
    detection_thread.start()
    
    # 初回起動
    print("3秒後にモーター起動...")
    time.sleep(3)
    motor.start_next_rotation()
    
    rotation_count = 1
    person_detected_and_stopped = False
    
    try:
        print("✓ システム起動\n")
        
        while True:
            # 人がいなくなったら自動再開
            if person_detected_and_stopped and not detection_thread.stable_detection_flag and not motor.is_running:
                print("\n✓ 人消失 - 再開\n")
                time.sleep(1)
                motor.start_next_rotation()
                if not motor.rotation_interrupted:
                    rotation_count += 1
                person_detected_and_stopped = False
            
            # 人検出で停止フラグを立てる
            if detection_thread.stable_detection_flag and not motor.is_running:
                person_detected_and_stopped = True
            
            # 1回転完了チェック
            if motor.check_rotation_complete():
                print(f"\n✓ 1回転完了 ({motor.direction})\n")
                motor.normal_stop()
                motor.switch_direction()
                time.sleep(1)
                
                if not detection_thread.stable_detection_flag:
                    motor.start_next_rotation()
                    rotation_count += 1
                else:
                    print("⚠ 人検出中 - 待機")
                    person_detected_and_stopped = True
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n\n終了")
    
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nクリーンアップ中...")
        
        stop_event.set()
        detection_thread.join(timeout=2)
        
        if motor.is_running:
            motor.emergency_stop()
        
        cap.release()
        
        GPIO.output(START_STOP, OFF)
        GPIO.output(RUN_BRAKE, OFF)
        GPIO.output(CW_CCW, OFF)
        GPIO.output(INT_VR_EXT, OFF)
        time.sleep(0.5)
        GPIO.cleanup()
        
        print("✓ クリーンアップ完了")
        print(f"総回転回数: {rotation_count}")
        print(f"総検出回数: {person_detector.detection_count}")
        print("終了\n")

if __name__ == "__main__":
    main()
