#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import cv2
import numpy as np
from nanodet import NanoDetONNX
import threading
from queue import Queue

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
ROTATION_TIME = 3.0  # 1回転にかかる時間（秒）

# ===================================
# 物体検出設定（超軽量化）
# ===================================
DETECTION_THRESHOLD = 0.3  # 人検出の信頼度閾値
<<<<<<< HEAD
STABLE_DETECTION_COUNT = 1  # 安定検出に必要な連続フレーム数
=======
STABLE_DETECTION_COUNT = 2  # 2フレームに削減（瞬時停止のため）
>>>>>>> 0b01c19b348eb46424dfd5acf9229ca35ab25486
PERSON_CLASS_ID = 0  # COCOデータセットの人クラスID

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
        self.lock = threading.Lock()  # スレッドセーフ
    
    def initialize(self):
        """モーターを初期化"""
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
        """CW方向で起動"""
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
        """CCW方向で起動"""
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
        """次の方向で1回転を開始"""
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
        """次回の回転方向を切り替え"""
        with self.lock:
            self.current_direction_cw = not self.current_direction_cw
            self.elapsed_time_before_stop = 0.0
            self.rotation_interrupted = False
        print(f"🔄 次: {'CW' if self.current_direction_cw else 'CCW'}")
    
    def check_rotation_complete(self):
        """1回転が完了したかチェック"""
        with self.lock:
            if not self.is_running or self.rotation_start_time is None:
                return False
            elapsed = time.time() - self.rotation_start_time
            return elapsed >= self.rotation_time
    
    def get_remaining_time(self):
        """残り回転時間を取得"""
        with self.lock:
            if not self.is_running or self.rotation_start_time is None:
                remaining = max(0.0, self.rotation_time - self.elapsed_time_before_stop)
                return remaining
            elapsed = time.time() - self.rotation_start_time
            remaining = max(0.0, self.rotation_time - elapsed)
            return remaining
    
    def emergency_stop(self):
        """緊急停止 - 即座に実行"""
        with self.lock:
            if not self.is_running:
                return
            
            print("🛑 緊急停止!")
            
            if self.rotation_start_time is not None:
                self.elapsed_time_before_stop = time.time() - self.rotation_start_time
                self.rotation_interrupted = True
            
            # GPIO操作は最優先
            GPIO.output(RUN_BRAKE, OFF)
            GPIO.output(START_STOP, OFF)
            
            self.is_running = False
            self.direction = "STOP"
            self.rotation_start_time = None
    
    def normal_stop(self):
        """通常停止"""
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

class FastPersonDetector:
    """超高速物体検出クラス"""
    
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
                    break
            
            if model_path is None:
                raise FileNotFoundError("NanoDetモデルファイルが見つかりません")
        
        # 最小サイズで初期化（160x160）
        self.detector = NanoDetONNX(
            model_path=model_path,
            input_shape=160,  # 320 → 160（4倍高速化）
            class_score_th=DETECTION_THRESHOLD,
            nms_th=0.6,
        )
        self.stable_count = 0
        print("✓ 検出モデル読み込み完了（超軽量版: 160x160）")
    
    def detect_person(self, frame):
        """超高速検出（最小サイズ）"""
        # 極小サイズで検出（80x60）
        tiny_frame = cv2.resize(frame, (80, 60), interpolation=cv2.INTER_NEAREST)
        
        bboxes, scores, class_ids = self.detector.inference(tiny_frame)
        
        person_count = sum(
            1 for i, cid in enumerate(class_ids) 
            if cid == PERSON_CLASS_ID and scores[i] >= DETECTION_THRESHOLD
        )
        
        person_detected = person_count > 0
        
        if person_detected:
            self.stable_count += 1
        else:
            self.stable_count = 0
        
        stable_detection = self.stable_count >= STABLE_DETECTION_COUNT
        
        return person_detected, person_count, stable_detection

class DetectionThread(threading.Thread):
    """検出専用スレッド（バックグラウンドで常時監視）"""
    
    def __init__(self, cap, detector, motor, stop_event):
        super().__init__(daemon=True)
        self.cap = cap
        self.detector = detector
        self.motor = motor
        self.stop_event = stop_event
        self.person_detected_flag = False
        self.stable_detection_flag = False
    
    def run(self):
        """検出ループ（別スレッドで実行）"""
        print("🔍 検出スレッド起動")
        
        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            # 超高速検出
            person_detected, person_count, stable_detection = self.detector.detect_person(frame)
            
            self.person_detected_flag = person_detected
            self.stable_detection_flag = stable_detection
            
            # 安定検出したら即座にモーター停止
            if stable_detection and self.motor.is_running:
                print(f"👤 人検出! ({person_count}人) - 即座に停止")
                self.motor.emergency_stop()
            
            # CPU負荷軽減（わずかなスリープ）
            time.sleep(0.005)
        
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
    person_detector = FastPersonDetector()
    
    # カメラ初期化（最小解像度）
    print("📷 カメラ初期化中...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 160)  # 超低解像度
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # バッファ最小化
    
    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        return
    
    print("✓ カメラ初期化完了（160x120）")
    print()
    print("=" * 60)
    print("超軽量・瞬時停止対応モーター制御システム")
    print("=" * 60)
    print("最適化:")
    print("  - 検出を別スレッドで実行（メインループ非ブロッキング）")
    print("  - 超低解像度（160x120 → 80x60で検出）")
    print("  - 検出モデル入力サイズ最小化（160x160）")
    print("  - 人検出 → 即座にモーター停止")
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
    last_status_time = time.time()
    
    try:
        print("✓ システム起動\n")
        
        while True:
            # 定期的にステータス表示（3秒ごと）
            current_time = time.time()
            if current_time - last_status_time >= 3.0:
                print(f"[状態] Motor: {'ON' if motor.is_running else 'OFF'} | "
                      f"{motor.direction} | "
                      f"Person: {'YES' if detection_thread.person_detected_flag else 'NO'} | "
                      f"Stable: {person_detector.stable_count}/{STABLE_DETECTION_COUNT} | "
                      f"回転: {rotation_count}")
                last_status_time = current_time
            
            # 人がいなくなったら自動再開
            if person_detected_and_stopped and not detection_thread.stable_detection_flag and not motor.is_running:
                print("✓ 人消失 - 再開")
                time.sleep(0.5)
                motor.start_next_rotation()
                if not motor.rotation_interrupted:
                    rotation_count += 1
                person_detected_and_stopped = False
            
            # 人検出で停止フラグを立てる
            if detection_thread.stable_detection_flag and not motor.is_running:
                person_detected_and_stopped = True
            
            # 1回転完了チェック
            if motor.check_rotation_complete():
                print(f"✓ 1回転完了 ({motor.direction})")
                motor.normal_stop()
                motor.switch_direction()
                time.sleep(0.5)
                
                if not detection_thread.stable_detection_flag:
                    motor.start_next_rotation()
                    rotation_count += 1
                else:
                    print("⚠ 人検出中 - 待機")
                    person_detected_and_stopped = True
            
            time.sleep(0.02)  # メインループ
    
    except KeyboardInterrupt:
        print("\n\n終了")
    
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nクリーンアップ中...")
        
        # 検出スレッド停止
        stop_event.set()
        detection_thread.join(timeout=2)
        
        # モーター停止
        if motor.is_running:
            motor.emergency_stop()
        
        # カメラ解放
        cap.release()
        
        # GPIO解放
        GPIO.output(START_STOP, OFF)
        GPIO.output(RUN_BRAKE, OFF)
        GPIO.output(CW_CCW, OFF)
        GPIO.output(INT_VR_EXT, OFF)
        time.sleep(0.5)
        GPIO.cleanup()
        
        print("✓ クリーンアップ完了")
        print(f"総回転回数: {rotation_count}")
        print("終了\n")

if __name__ == "__main__":
    main()
