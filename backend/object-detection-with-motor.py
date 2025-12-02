#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物体検出統合型モーター制御システム
人を検出したらモーターを自動停止する安全機能付き
"""
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
# 物体検出設定
# ===================================
DETECTION_THRESHOLD = 0.6  # 人検出の信頼度閾値
STABLE_DETECTION_COUNT = 3  # 安定検出に必要な連続フレーム数
PERSON_CLASS_ID = 0  # COCOデータセットの人クラスID

# ===================================
# グローバル変数
# ===================================
motor_running = False
detector = None

class MotorController:
    """BLHモーター制御クラス"""
    
    def __init__(self):
        self.is_initialized = False
        self.is_running = False
        self.direction = "STOP"
    
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
        print("✓ CCW方向で回転中")
        return True
    
    def emergency_stop(self):
        """緊急停止（ブレーキ適用）"""
        print("🛑 緊急停止実行!")
        GPIO.output(RUN_BRAKE, OFF)  # ブレーキ
        time.sleep(0.2)
        GPIO.output(START_STOP, OFF)  # 停止
        
        self.is_running = False
        self.direction = "STOP"
        print("✓ モーター停止完了")
    
    def normal_stop(self):
        """通常停止"""
        if not self.is_running:
            return
        
        print("⏹ 通常停止中...")
        GPIO.output(RUN_BRAKE, OFF)  # ブレーキ
        time.sleep(0.5)
        GPIO.output(START_STOP, OFF)  # 停止
        
        self.is_running = False
        self.direction = "STOP"
        print("✓ モーター停止完了")
    
    def get_status(self):
        """現在の状態を取得"""
        return {
            'initialized': self.is_initialized,
            'running': self.is_running,
            'direction': self.direction
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
    motor = MotorController()
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
    print("物体検出統合型モーター制御システム")
    print("=" * 60)
    print("機能:")
    print("  - 人を検出したらモーターを自動停止")
    print("  - キーボード操作:")
    print("    [s] CW方向で起動")
    print("    [d] CCW方向で起動")
    print("    [f] 通常停止")
    print("    [SPACE] 緊急停止")
    print("    [q] 終了")
    print("=" * 60)
    print()
    
    # モーターを起動（デフォルトCW）
    print("3秒後にCW方向でモーター起動...")
    time.sleep(3)
    motor.start_cw()
    
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
                print("⚠ 安全のためモーターを停止しました")
                print("  再開するには [s] または [d] を押してください")
            
            # 検出結果を描画
            bboxes, scores, class_ids = person_detector.detector.inference(frame)
            frame = person_detector.draw_detections(frame, bboxes, scores, class_ids)
            
            # ステータス表示
            status = motor.get_status()
            status_text = f"Motor: {'ON' if status['running'] else 'OFF'} | Direction: {status['direction']}"
            detection_text = f"Person: {'YES' if person_detected else 'NO'} | Count: {person_count} | Stable: {person_detector.stable_count}/{STABLE_DETECTION_COUNT}"
            
            cv2.putText(frame, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, detection_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            
            # 画面表示
            cv2.imshow('Motor Control with Person Detection', frame)
            
            # キーボード入力処理
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\n終了します...")
                break
            
            elif key == ord('s'):
                if not motor.is_running:
                    motor.start_cw()
                else:
                    print("⚠ モーターは既に動作中です")
            
            elif key == ord('d'):
                if not motor.is_running:
                    motor.start_ccw()
                else:
                    print("⚠ モーターは既に動作中です")
            
            elif key == ord('f'):
                motor.normal_stop()
            
            elif key == ord(' '):
                motor.emergency_stop()
    
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
        print("プログラムを終了します\n")

if __name__ == "__main__":
    main()
