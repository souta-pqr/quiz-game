#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import cv2
import numpy as np
from nanodet import NanoDetONNX

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
# 物体検出設定
# ===================================
DETECTION_THRESHOLD = 0.3  # 人検出の信頼度閾値
STABLE_DETECTION_COUNT = 3  # 安定検出に必要な連続フレーム数
PERSON_CLASS_ID = 0  # COCOデータセットの人クラスID
DETECTION_INTERVAL = 3  # 検出を実行するフレーム間隔（フレームをスキップ）

class MotorController:
    """BLHモーター制御クラス（回転位置保存版）"""
    
    def __init__(self, rotation_time=ROTATION_TIME):
        self.is_initialized = False
        self.is_running = False
        self.direction = "STOP"
        self.rotation_time = rotation_time
        self.current_direction_cw = True
        self.rotation_start_time = None
        self.elapsed_time_before_stop = 0.0
        self.rotation_interrupted = False
    
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
        print(f"  1回転時間: {self.rotation_time}秒")
    
    def start_cw(self):
        """CW方向で起動"""
        if not self.is_initialized:
            print("⚠ モーターが初期化されていません")
            return False
        
        print("▶ CW方向で起動...")
        GPIO.output(CW_CCW, ON)
        time.sleep(0.1)
        GPIO.output(START_STOP, ON)
        time.sleep(0.5)
        GPIO.output(RUN_BRAKE, ON)
        
        self.is_running = True
        self.direction = "CW"
        self.rotation_start_time = time.time()
        print("✓ CW方向で回転中")
        return True
    
    def start_ccw(self):
        """CCW方向で起動"""
        if not self.is_initialized:
            print("⚠ モーターが初期化されていません")
            return False
        
        print("▶ CCW方向で起動...")
        GPIO.output(CW_CCW, OFF)
        time.sleep(0.1)
        GPIO.output(START_STOP, ON)
        time.sleep(0.5)
        GPIO.output(RUN_BRAKE, ON)
        
        self.is_running = True
        self.direction = "CCW"
        self.rotation_start_time = time.time()
        print("✓ CCW方向で回転中")
        return True
    
    def start_next_rotation(self):
        """次の方向で1回転を開始（中断していた場合は継続）"""
        if self.rotation_interrupted:
            print(f"🔄 中断された回転を再開（残り{self.get_remaining_time():.1f}秒）")
            self.rotation_interrupted = False
            if self.current_direction_cw:
                self.start_cw()
            else:
                self.start_ccw()
            self.rotation_start_time -= self.elapsed_time_before_stop
        else:
            if self.current_direction_cw:
                self.start_cw()
            else:
                self.start_ccw()
    
    def switch_direction(self):
        """次回の回転方向を切り替え"""
        self.current_direction_cw = not self.current_direction_cw
        self.elapsed_time_before_stop = 0.0
        self.rotation_interrupted = False
        print(f"🔄 次の回転方向: {'CW' if self.current_direction_cw else 'CCW'}")
    
    def check_rotation_complete(self):
        """1回転が完了したかチェック"""
        if not self.is_running or self.rotation_start_time is None:
            return False
        elapsed = time.time() - self.rotation_start_time
        return elapsed >= self.rotation_time
    
    def get_remaining_time(self):
        """残り回転時間を取得"""
        if not self.is_running or self.rotation_start_time is None:
            remaining = max(0.0, self.rotation_time - self.elapsed_time_before_stop)
            return remaining
        elapsed = time.time() - self.rotation_start_time
        remaining = max(0.0, self.rotation_time - elapsed)
        return remaining
    
    def emergency_stop(self):
        """緊急停止 - 回転位置を保存"""
        print("🛑 緊急停止実行!")
        
        if self.is_running and self.rotation_start_time is not None:
            self.elapsed_time_before_stop = time.time() - self.rotation_start_time
            self.rotation_interrupted = True
            progress = (self.elapsed_time_before_stop / self.rotation_time) * 100.0
            print(f"  回転位置を保存: {self.elapsed_time_before_stop:.2f}秒経過 (進捗: {progress:.1f}%)")
        
        GPIO.output(RUN_BRAKE, OFF)
        time.sleep(0.2)
        GPIO.output(START_STOP, OFF)
        
        self.is_running = False
        self.direction = "STOP"
        self.rotation_start_time = None
        print("✓ モーター停止完了")
    
    def normal_stop(self):
        """通常停止"""
        if not self.is_running:
            return
        
        print("⏹ 通常停止中...")
        GPIO.output(RUN_BRAKE, OFF)
        time.sleep(0.5)
        GPIO.output(START_STOP, OFF)
        
        self.is_running = False
        self.direction = "STOP"
        self.rotation_start_time = None
        self.elapsed_time_before_stop = 0.0
        self.rotation_interrupted = False
        print("✓ モーター停止完了")

class PersonDetector:
    """物体検出クラス（軽量化版）"""
    
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
                    print(f"✓ モデルファイル発見: {model_path}")
                    break
            
            if model_path is None:
                print("❌ モデルファイルが見つかりません")
                raise FileNotFoundError("NanoDetモデルファイルが見つかりません")
        
        self.detector = NanoDetONNX(
            model_path=model_path,
            input_shape=320,  # 320x320で高速化
            class_score_th=DETECTION_THRESHOLD,
            nms_th=0.6,
        )
        self.stable_count = 0
        print("✓ 物体検出モデル読み込み完了")
    
    def detect_person(self, frame):
        """フレームから人を検出（軽量化版）
        
        Returns:
            tuple: (person_detected, person_count, stable_detection)
        """
        # 画像を縮小して高速化（320x240）
        small_frame = cv2.resize(frame, (320, 240))
        
        bboxes, scores, class_ids = self.detector.inference(small_frame)
        
        # 人クラスのみをフィルタリング
        person_count = sum(
            1 for i, cid in enumerate(class_ids) 
            if cid == PERSON_CLASS_ID and scores[i] >= DETECTION_THRESHOLD
        )
        
        person_detected = person_count > 0
        
        # 安定検出判定
        if person_detected:
            self.stable_count += 1
        else:
            self.stable_count = 0
        
        stable_detection = self.stable_count >= STABLE_DETECTION_COUNT
        
        return person_detected, person_count, stable_detection

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
    person_detector = PersonDetector()
    
    # カメラ初期化（解像度を下げて高速化）
    print("📷 カメラ初期化中...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)  # 640 → 320
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)  # 480 → 240
    cap.set(cv2.CAP_PROP_FPS, 15)  # FPSを15に制限
    
    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        return
    
    print("✓ カメラ初期化完了（320x240 @ 15fps）")
    print()
    print("=" * 60)
    print("物体検出統合型モーター制御システム（軽量化版）")
    print("=" * 60)
    print("最適化:")
    print("  - 画面表示なし（処理速度優先）")
    print("  - 検出頻度削減（3フレームに1回）")
    print("  - カメラ解像度削減（320x240）")
    print("機能:")
    print("  - モーターをCWとCCWで交互に1回転ずつ実行")
    print("  - 人を検出したらモーターを自動停止（回転位置を保存）")
    print("  - 人がいなくなったら中断した回転を再開")
    print("  - Ctrl+C で終了")
    print("=" * 60)
    print()
    
    # 初回起動
    print("3秒後に自動的にモーター起動（CW方向）...")
    time.sleep(3)
    motor.start_next_rotation()
    
    rotation_count = 1
    person_detected_and_stopped = False
    frame_count = 0
    last_detection_time = time.time()
    
    try:
        print("✓ システム起動 - 物体検出開始")
        print("  ステータスは定期的にコンソールに表示されます")
        print()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            
            frame_count += 1
            
            # 検出頻度を下げる（DETECTION_INTERVALフレームに1回だけ検出）
            if frame_count % DETECTION_INTERVAL != 0:
                # 1回転完了チェックだけは毎フレーム行う
                if motor.check_rotation_complete():
                    print(f"✓ 1回転完了! ({motor.direction}方向)")
                    motor.normal_stop()
                    motor.switch_direction()
                    time.sleep(1)
                    
                    # 人が検出されていなければ次の回転を開始
                    if not person_detected_and_stopped:
                        motor.start_next_rotation()
                        rotation_count += 1
                        print(f"  回転回数: {rotation_count}")
                    else:
                        print("⚠ 人を検出中のため次の回転を待機...")
                
                time.sleep(0.01)  # 短いスリープでCPU負荷軽減
                continue
            
            # 物体検出（間引いたフレームのみ）
            person_detected, person_count, stable_detection = person_detector.detect_person(frame)
            
            # 定期的にステータスを表示（5秒ごと）
            current_time = time.time()
            if current_time - last_detection_time >= 5.0:
                remaining = motor.get_remaining_time()
                print(f"[状態] Motor: {'ON' if motor.is_running else 'OFF'} | "
                      f"Dir: {motor.direction} | "
                      f"Person: {'YES' if person_detected else 'NO'} ({person_count}人) | "
                      f"Stable: {person_detector.stable_count}/{STABLE_DETECTION_COUNT} | "
                      f"Remaining: {remaining:.1f}s | "
                      f"Rotations: {rotation_count}")
                last_detection_time = current_time
            
            # 安定検出時にモーター停止
            if stable_detection and motor.is_running:
                print(f"👤 人を検出! ({person_count}人)")
                motor.emergency_stop()
                person_detected_and_stopped = True
                print("⚠ 安全のためモーターを停止しました")
                print("  人がいなくなれば自動的に再開します")
            
            # 人がいなくなったら自動再開
            if person_detected_and_stopped and not stable_detection and not motor.is_running:
                print("✓ 人がいなくなりました - 自動再開します")
                time.sleep(1)
                motor.start_next_rotation()
                if not motor.rotation_interrupted:
                    rotation_count += 1
                print(f"  回転回数: {rotation_count}")
                person_detected_and_stopped = False
            
            # 1回転完了チェック
            if motor.check_rotation_complete():
                print(f"✓ 1回転完了! ({motor.direction}方向)")
                motor.normal_stop()
                motor.switch_direction()
                time.sleep(1)
                
                if not stable_detection:
                    motor.start_next_rotation()
                    rotation_count += 1
                    print(f"  回転回数: {rotation_count}")
                else:
                    print("⚠ 人を検出中のため次の回転を待機...")
                    person_detected_and_stopped = True
            
            time.sleep(0.01)  # CPU負荷軽減
    
    except KeyboardInterrupt:
        print("\n\n割り込みを検出しました")
    
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nクリーンアップ中...")
        
        # モーターを安全に停止
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
        print("プログラムを終了します\n")

if __name__ == "__main__":
    main()
