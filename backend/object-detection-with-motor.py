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
ROTATION_TIME = 3.0  # 1回転にかかる時間（秒）※モーターの速度に応じて調整してください

# ===================================
# 物体検出設定
# ===================================
DETECTION_THRESHOLD = 0.3  # 人検出の信頼度閾値
STABLE_DETECTION_COUNT = 3  # 安定検出に必要な連続フレーム数
PERSON_CLASS_ID = 0  # COCOデータセットの人クラスID

# ===================================
# グローバル変数
# ===================================
motor_running = False
detector = None

class MotorController:
    """BLHモーター制御クラス（回転位置保存版）"""
    
    def __init__(self, rotation_time=ROTATION_TIME):
        """
        Args:
            rotation_time: 1回転にかかる時間（秒）
        """
        self.is_initialized = False
        self.is_running = False
        self.direction = "STOP"
        self.rotation_time = rotation_time
        self.current_direction_cw = True  # True=CW, False=CCW
        self.rotation_start_time = None
        self.elapsed_time_before_stop = 0.0  # 停止前の経過時間を保存
        self.rotation_interrupted = False  # 回転が中断されたかどうか
    
    def initialize(self):
        """モーターを初期化"""
        print("🔧 モーター初期化中...")
        GPIO.output(START_STOP, OFF)
        GPIO.output(RUN_BRAKE, OFF)
        GPIO.output(CW_CCW, OFF)
        GPIO.output(INT_VR_EXT, ON)  # 内部速度設定
        time.sleep(0.5)
        self.is_initialized = True
        self.is_running = False
        print("✓ モーター初期化完了")
        print(f"  1回転時間: {self.rotation_time}秒")
    
    def start_cw(self):
        """CW方向（時計回り）で起動"""
        if not self.is_initialized:
            print("⚠ モーターが初期化されていません")
            return False
        
        print("▶ CW方向で起動...")
        GPIO.output(CW_CCW, ON)  # CW方向
        time.sleep(0.1)
        GPIO.output(START_STOP, ON)  # モーター起動
        time.sleep(0.5)
        GPIO.output(RUN_BRAKE, ON)  # 運転
        
        self.is_running = True
        self.direction = "CW"
        self.rotation_start_time = time.time()
        print("✓ CW方向で回転中")
        return True
    
    def start_ccw(self):
        """CCW方向（反時計回り）で起動"""
        if not self.is_initialized:
            print("⚠ モーターが初期化されていません")
            return False
        
        print("▶ CCW方向で起動...")
        GPIO.output(CW_CCW, OFF)  # CCW方向
        time.sleep(0.1)
        GPIO.output(START_STOP, ON)  # モーター起動
        time.sleep(0.5)
        GPIO.output(RUN_BRAKE, ON)  # 運転
        
        self.is_running = True
        self.direction = "CCW"
        self.rotation_start_time = time.time()
        print("✓ CCW方向で回転中")
        return True
    
    def start_next_rotation(self):
        """次の方向で1回転を開始（中断していた場合は継続）"""
        if self.rotation_interrupted:
            # 中断された回転を再開
            print(f"🔄 中断された回転を再開（残り{self.get_remaining_time():.1f}秒）")
            self.rotation_interrupted = False
            # 経過時間を考慮して開始時刻を調整
            if self.current_direction_cw:
                self.start_cw()
            else:
                self.start_ccw()
            # 開始時刻を過去に戻して、残り時間を正しく計算
            self.rotation_start_time -= self.elapsed_time_before_stop
        else:
            # 新しい回転を開始
            if self.current_direction_cw:
                self.start_cw()
            else:
                self.start_ccw()
    
    def switch_direction(self):
        """次回の回転方向を切り替え（1回転完了時のみ）"""
        self.current_direction_cw = not self.current_direction_cw
        self.elapsed_time_before_stop = 0.0
        self.rotation_interrupted = False
        print(f"🔄 次の回転方向: {'CW' if self.current_direction_cw else 'CCW'}")
    
    def check_rotation_complete(self):
        """1回転が完了したかチェック
        
        Returns:
            bool: 1回転完了したらTrue
        """
        if not self.is_running or self.rotation_start_time is None:
            return False
        
        elapsed = time.time() - self.rotation_start_time
        return elapsed >= self.rotation_time
    
    def get_elapsed_time(self):
        """現在の経過時間を取得
        
        Returns:
            float: 経過時間（秒）
        """
        if not self.is_running or self.rotation_start_time is None:
            return self.elapsed_time_before_stop
        
        return time.time() - self.rotation_start_time
    
    def get_remaining_time(self):
        """残り回転時間を取得
        
        Returns:
            float: 残り時間（秒）
        """
        if not self.is_running or self.rotation_start_time is None:
            # 停止中の場合、停止前の経過時間から残り時間を計算
            remaining = max(0.0, self.rotation_time - self.elapsed_time_before_stop)
            return remaining
        
        elapsed = time.time() - self.rotation_start_time
        remaining = max(0.0, self.rotation_time - elapsed)
        return remaining
    
    def get_rotation_progress(self):
        """回転の進捗を取得（パーセント）
        
        Returns:
            float: 進捗（0.0 ~ 100.0）
        """
        if self.rotation_time == 0:
            return 0.0
        
        elapsed = self.get_elapsed_time()
        progress = min(100.0, (elapsed / self.rotation_time) * 100.0)
        return progress
    
    def emergency_stop(self):
        """緊急停止（ブレーキ適用）- 回転位置を保存"""
        print("🛑 緊急停止実行!")
        
        # 現在の経過時間を保存
        if self.is_running and self.rotation_start_time is not None:
            self.elapsed_time_before_stop = time.time() - self.rotation_start_time
            self.rotation_interrupted = True
            print(f"  回転位置を保存: {self.elapsed_time_before_stop:.2f}秒経過 (進捗: {self.get_rotation_progress():.1f}%)")
        
        GPIO.output(RUN_BRAKE, OFF)  # ブレーキ
        time.sleep(0.2)
        GPIO.output(START_STOP, OFF)  # 停止
        
        self.is_running = False
        self.direction = "STOP"
        self.rotation_start_time = None
        print("✓ モーター停止完了")
    
    def normal_stop(self):
        """通常停止（1回転完了時）"""
        if not self.is_running:
            return
        
        print("⏹ 通常停止中...")
        GPIO.output(RUN_BRAKE, OFF)  # ブレーキ
        time.sleep(0.5)
        GPIO.output(START_STOP, OFF)  # 停止
        
        self.is_running = False
        self.direction = "STOP"
        self.rotation_start_time = None
        # 1回転完了なのでリセット
        self.elapsed_time_before_stop = 0.0
        self.rotation_interrupted = False
        print("✓ モーター停止完了")
    
    def get_status(self):
        """現在の状態を取得"""
        return {
            'initialized': self.is_initialized,
            'running': self.is_running,
            'direction': self.direction,
            'next_direction': 'CW' if self.current_direction_cw else 'CCW',
            'remaining_time': self.get_remaining_time(),
            'elapsed_time': self.get_elapsed_time(),
            'progress': self.get_rotation_progress(),
            'interrupted': self.rotation_interrupted
        }

class PersonDetector:
    """物体検出クラス"""
    
    def __init__(self, model_path=None):
        print("🔍 物体検出モデル読み込み中...")
        
        # モデルパスの自動検出
        if model_path is None:
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 複数の候補パスを試す
            possible_paths = [
                os.path.join(script_dir, 'model', 'nanodet_m_320.onnx'),  # backend/model/
                os.path.join(script_dir, 'backend', 'model', 'nanodet_m_320.onnx'),  # ../backend/model/
                '/home/fujielab-raspi5/work/quiz-game/backend/model/nanodet_m_320.onnx',  # 絶対パス
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    model_path = path
                    print(f"✓ モデルファイル発見: {model_path}")
                    break
            
            if model_path is None:
                print("❌ モデルファイルが見つかりません")
                print("以下のパスを確認してください:")
                for path in possible_paths:
                    print(f"  - {path}")
                raise FileNotFoundError("NanoDetモデルファイルが見つかりません")
        
        self.detector = NanoDetONNX(
            model_path=model_path,
            input_shape=320,
            class_score_th=DETECTION_THRESHOLD,
            nms_th=0.6,
        )
        self.stable_count = 0
        print("✓ 物体検出モデル読み込み完了")
    
    def detect_person(self, frame):
        """フレームから人を検出
        
        Returns:
            tuple: (person_detected, person_count, stable_detection)
        """
        bboxes, scores, class_ids = self.detector.inference(frame)
        
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
    
    def draw_detections(self, frame, bboxes, scores, class_ids):
        """検出結果を描画"""
        for i, (bbox, score, class_id) in enumerate(zip(bboxes, scores, class_ids)):
            if class_id == PERSON_CLASS_ID and score >= DETECTION_THRESHOLD:
                x1, y1, x2, y2 = bbox
                
                # バウンディングボックス
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                
                # ラベル
                label = f"Person: {score:.2f}"
                cv2.putText(
                    frame, label, (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2
                )
        
        return frame

def main():
    """メイン処理"""
    global motor_running, detector
    
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
    
    # カメラ初期化
    print("📷 カメラ初期化中...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("❌ カメラを開けませんでした")
        return
    
    print("✓ カメラ初期化完了")
    print()
    print("=" * 60)
    print("物体検出統合型モーター制御システム（回転位置保存版）")
    print("=" * 60)
    print("機能:")
    print("  - モーターをCWとCCWで交互に1回転ずつ実行")
    print("  - 人を検出したらモーターを自動停止（回転位置を保存）")
    print("  - 人がいなくなったら中断した回転を再開")
    print("  - キーボード操作:")
    print("    [SPACE] 緊急停止")
    print("    [r] 手動で再開（中断していた回転を継続）")
    print("    [q] 終了")
    print("=" * 60)
    print()
    
    # 初回起動
    print("3秒後に自動的にモーター起動（CW方向）...")
    time.sleep(3)
    motor.start_next_rotation()
    
    rotation_count = 1
    person_detected_and_stopped = False
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠ フレーム取得失敗")
                time.sleep(0.1)
                continue
            
            # 物体検出
            person_detected, person_count, stable_detection = person_detector.detect_person(frame)
            
            # 安定検出時にモーター停止
            if stable_detection and motor.is_running:
                print(f"👤 人を検出! ({person_count}人)")
                motor.emergency_stop()
                person_detected_and_stopped = True
                print("⚠ 安全のためモーターを停止しました")
                print("  人がいなくなれば自動的に再開します")
            
            # 人がいなくなったら自動再開（中断した回転を継続）
            if person_detected_and_stopped and not stable_detection and not motor.is_running:
                print("✓ 人がいなくなりました - 自動再開します")
                time.sleep(1)  # 少し待機
                motor.start_next_rotation()
                # 回転カウントは中断再開時は増やさない
                if not motor.rotation_interrupted:
                    rotation_count += 1
                print(f"  回転回数: {rotation_count}")
                person_detected_and_stopped = False
            
            # 1回転完了チェック
            if motor.check_rotation_complete():
                print(f"✓ 1回転完了! ({motor.direction}方向)")
                motor.normal_stop()
                
                # 次の方向に切り替え
                motor.switch_direction()
                
                # 少し待機してから次の回転を開始
                time.sleep(1)
                
                # 人が検出されていなければ次の回転を開始
                if not stable_detection:
                    motor.start_next_rotation()
                    rotation_count += 1
                    print(f"  回転回数: {rotation_count}")
                else:
                    print("⚠ 人を検出中のため次の回転を待機...")
                    person_detected_and_stopped = True
            
            # 検出結果を描画
            bboxes, scores, class_ids = person_detector.detector.inference(frame)
            frame = person_detector.draw_detections(frame, bboxes, scores, class_ids)
            
            # ステータス表示
            status = motor.get_status()
            status_text = f"Motor: {'ON' if status['running'] else 'OFF'} | Dir: {status['direction']} | Next: {status['next_direction']}"
            detection_text = f"Person: {'YES' if person_detected else 'NO'} | Count: {person_count} | Stable: {person_detector.stable_count}/{STABLE_DETECTION_COUNT}"
            rotation_text = f"Rotations: {rotation_count} | Progress: {status['progress']:.1f}% | Remaining: {status['remaining_time']:.1f}s"
            interrupted_text = ""
            if status['interrupted']:
                interrupted_text = f"[INTERRUPTED - Resume from {status['elapsed_time']:.1f}s]"
            
            cv2.putText(frame, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, detection_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            cv2.putText(frame, rotation_text, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            if interrupted_text:
                cv2.putText(frame, interrupted_text, (10, 120),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            
            # 画面表示
            cv2.imshow('Motor Control - Position Saving', frame)
            
            # キーボード入力処理
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\n終了します...")
                break
            
            elif key == ord(' '):
                motor.emergency_stop()
                person_detected_and_stopped = False
            
            elif key == ord('r'):
                if not motor.is_running and not stable_detection:
                    print("手動再開...")
                    motor.start_next_rotation()
                    # 回転カウントは中断再開時は増やさない
                    if not motor.rotation_interrupted:
                        rotation_count += 1
                    print(f"  回転回数: {rotation_count}")
                    person_detected_and_stopped = False
                elif stable_detection:
                    print("⚠ 人を検出中のため再開できません")
                else:
                    print("⚠ モーターは既に動作中です")
    
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
        cv2.destroyAllWindows()
        
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
