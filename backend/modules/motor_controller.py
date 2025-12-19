#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
モーター制御モジュール
BLHモーター制御クラス（位置追跡・ランダム回転機能付き）
"""

import time
import threading
import random
from .gpio_controller import GPIOWrapper, GPIO_AVAILABLE, ON, OFF, START_STOP, RUN_BRAKE, CW_CCW, INT_VR_EXT


# ===================================
# モーター設定
# ===================================
HALF_ROTATION_TIME = 0.9  # 半回転（180°）にかかる時間
STEP_DURATION = 0.15
STEP_PAUSE = 0.50


class MotorController:
    """BLHモーター制御クラス (位置追跡・ランダム回転機能付き)"""
    
    def __init__(self, half_rotation_time=HALF_ROTATION_TIME):
        self.is_initialized = False
        self._is_running = False
        self.direction = "STOP"
        self.half_rotation_time = half_rotation_time
        self.current_direction_cw = False
        self.rotation_start_time = None
        self.elapsed_time = 0.0
        self.rotation_interrupted = False
        self.lock = threading.RLock()
        self._emergency_stop_requested = False
        
        self.rotation_phase = "ccw_cycle"
        self.phase_count = 0
        self.total_rotations = 0
        
        # 位置追跡（角度: -90° 〜 +90°）
        self.current_angle = 0.0      # 中央位置を0°とする
        self.MIN_ANGLE = -90.0        # CCW最大位置
        self.MAX_ANGLE = 90.0         # CW最大位置
        self.degrees_per_second = 180.0 / half_rotation_time  # 約200°/秒
        
        print(f"✓ モーター制御初期化: 回転速度={self.degrees_per_second:.1f}°/秒")
        print(f"  可動範囲: {self.MIN_ANGLE}° 〜 {self.MAX_ANGLE}°")
    
    @property
    def is_running(self):
        with self.lock:
            return self._is_running
    
    @is_running.setter
    def is_running(self, value):
        with self.lock:
            self._is_running = value
    
    def initialize(self):
        """モーター初期化"""
        print("🔧 モーター初期化中...")
        try:
            if GPIO_AVAILABLE:
                # GPIO初期設定を実行
                GPIOWrapper.output(START_STOP, OFF)
                GPIOWrapper.output(RUN_BRAKE, OFF)
                GPIOWrapper.output(CW_CCW, OFF)
                GPIOWrapper.output(INT_VR_EXT, ON)
                time.sleep(0.5)
                print("✓ GPIO出力設定完了")
            else:
                print("ℹ️ ダミーモードで初期化")
            
            with self.lock:
                self.is_initialized = True
                self._is_running = False
                self.rotation_phase = "ccw_cycle"
                self.current_direction_cw = False
                self.phase_count = 0
                self.total_rotations = 0
                self.current_angle = 0.0  # 中央位置でスタート
            
            print("✓ モーター初期化完了（位置: 0°）")
        except Exception as e:
            print(f"❌ モーター初期化エラー: {e}")
            raise
    
    def _update_angle(self, is_cw, duration):
        """角度位置を更新
        
        Args:
            is_cw: Trueなら時計回り（正の方向）
            duration: 回転時間（秒）
        """
        with self.lock:
            degrees_moved = self.degrees_per_second * duration
            if is_cw:
                self.current_angle += degrees_moved
                # 範囲制限
                if self.current_angle > self.MAX_ANGLE:
                    self.current_angle = self.MAX_ANGLE
            else:
                self.current_angle -= degrees_moved
                # 範囲制限
                if self.current_angle < self.MIN_ANGLE:
                    self.current_angle = self.MIN_ANGLE
            
            print(f"📍 現在位置: {self.current_angle:.1f}°")
    
    def _execute_step_with_check(self, is_cw):
        """ステップ実行（緊急停止チェック付き）"""
        with self.lock:
            if self._emergency_stop_requested:
                return False
        
        try:
            if GPIO_AVAILABLE:
                GPIOWrapper.output(CW_CCW, ON if is_cw else OFF)
                time.sleep(0.01)
                GPIOWrapper.output(START_STOP, ON)
                time.sleep(0.01)
                GPIOWrapper.output(RUN_BRAKE, ON)
            
            # 回転時間
            rotation_steps = 6
            step_interval = STEP_DURATION / rotation_steps
            
            for i in range(rotation_steps):
                with self.lock:
                    if self._emergency_stop_requested:
                        if GPIO_AVAILABLE:
                            GPIOWrapper.output(RUN_BRAKE, OFF)
                            time.sleep(0.01)
                            GPIOWrapper.output(START_STOP, OFF)
                        return False
                time.sleep(step_interval)
            
            if GPIO_AVAILABLE:
                GPIOWrapper.output(RUN_BRAKE, OFF)
                time.sleep(0.01)
                GPIOWrapper.output(START_STOP, OFF)
            
            # 角度位置を更新
            self._update_angle(is_cw, STEP_DURATION)
            
            # 停止時間
            pause_steps = 10
            pause_interval = STEP_PAUSE / pause_steps
            
            for i in range(pause_steps):
                with self.lock:
                    if self._emergency_stop_requested:
                        return False
                time.sleep(pause_interval)
            
            return True
            
        except Exception as e:
            print(f"❌ ステップ実行エラー: {e}")
            return False
    
    def start_slow_rotation(self):
        """断続運転開始"""
        with self.lock:
            if not self.is_initialized or self._is_running:
                return False
            
            direction_str = "CW" if self.current_direction_cw else "CCW"
            print(f"▶ {direction_str}断続運転開始（現在位置: {self.current_angle:.1f}°）")
            
            self._is_running = True
            self._emergency_stop_requested = False
            self.direction = direction_str
            self.rotation_start_time = time.time()
            self.elapsed_time = 0.0
            return True
    
    def execute_one_step(self):
        """1ステップ実行"""
        with self.lock:
            if not self._is_running:
                return False
            
            if self._emergency_stop_requested:
                self._perform_emergency_stop()
                return False
        
        try:
            step_start = time.time()
            success = self._execute_step_with_check(self.current_direction_cw)
            
            if not success:
                with self.lock:
                    self._perform_emergency_stop()
                return False
            
            step_time = time.time() - step_start
            
            with self.lock:
                self.elapsed_time += step_time
            return True
        except Exception as e:
            print(f"❌ ステップ実行中エラー: {e}")
            with self.lock:
                self._is_running = False
            return False
    
    def check_rotation_complete(self):
        """半回転完了チェック"""
        with self.lock:
            if not self._is_running:
                return False
            return self.elapsed_time >= self.half_rotation_time
    
    def request_emergency_stop(self):
        """緊急停止リクエスト"""
        with self.lock:
            if not self._is_running:
                return
            print(f"🚨 緊急停止リクエスト受信（現在位置: {self.current_angle:.1f}°）")
            self._emergency_stop_requested = True
    
    def _perform_emergency_stop(self):
        """緊急停止実行"""
        try:
            print(f"🛑 緊急停止実行中...")
            
            if GPIO_AVAILABLE:
                GPIOWrapper.output(RUN_BRAKE, OFF)
                time.sleep(0.1)
                GPIOWrapper.output(START_STOP, OFF)
            
            self.rotation_interrupted = True
            self._emergency_stop_requested = False
            self._reset_state_after_stop()
            
            print(f"✓ 緊急停止完了（最終位置: {self.current_angle:.1f}°）")
        except Exception as e:
            print(f"❌ 緊急停止中エラー: {e}")
    
    def normal_stop(self):
        """正常停止"""
        with self.lock:
            if not self._is_running:
                return
            
            try:
                print(f"⏹ 正常停止（位置: {self.current_angle:.1f}°）")
                if GPIO_AVAILABLE:
                    GPIOWrapper.output(RUN_BRAKE, OFF)
                    time.sleep(0.1)
                    GPIOWrapper.output(START_STOP, OFF)
                
                self.rotation_interrupted = False
                self._reset_state_after_stop()
                
                self.phase_count += 1
                self.total_rotations += 1
                
            except Exception as e:
                print(f"❌ 正常停止中エラー: {e}")

    def _reset_state_after_stop(self):
        """停止後の状態リセット"""
        self._is_running = False
        self.direction = "STOP"
        self.rotation_start_time = None
    
    def get_next_rotation_direction(self):
        """次の回転方向を決定"""
        with self.lock:
            if self.rotation_phase == "ccw_cycle":
                if self.phase_count >= 10:
                    self.rotation_phase = "cw_cycle"
                    self.phase_count = 0
                    self.current_direction_cw = True
                else:
                    self.current_direction_cw = False
            elif self.rotation_phase == "cw_cycle":
                if self.phase_count >= 10:
                    self.rotation_phase = "ccw_cycle"
                    self.phase_count = 0
                    self.current_direction_cw = False
                else:
                    self.current_direction_cw = True
            
            self.elapsed_time = 0.0
            self.rotation_interrupted = False
    
    def perform_random_rotation_for_reselection(self):
        """回答者再選択のためのランダム回転（CW/CCW交互動作）
        
        CWとCCWを交互にランダムな時間で回転（各最大0.7秒）
        合計1.0〜2.0秒間動作して、回答者を再選択する
        """
        with self.lock:
            if not self.is_initialized:
                print("⚠️ モーターが初期化されていません")
                return False
            
            print(f"\n🎲 回答者再選択: CW/CCW交互ランダム回転開始")
            print(f"   開始位置: {self.current_angle:.1f}°")
            
            # 合計回転時間の目標（1〜2秒）
            target_total_time = random.uniform(1.0, 2.0)
            print(f"   目標時間: {target_total_time:.2f}秒")
            
            # 各回転の最大時間
            max_single_rotation_time = 0.7  # 秒
            
            # 交互回転の実行
            total_elapsed = 0.0
            rotation_count = 0
            current_direction_is_cw = random.choice([True, False])  # 初回方向をランダムに
            
            print(f"   初回方向: {'CW' if current_direction_is_cw else 'CCW'}")
            print()
            
            try:
                while total_elapsed < target_total_time:
                    rotation_count += 1
                    
                    # 残り時間を計算
                    remaining_time = target_total_time - total_elapsed
                    
                    # 今回の回転時間を決定（残り時間と最大時間の小さい方）
                    max_this_time = min(max_single_rotation_time, remaining_time)
                    
                    # ランダムな回転時間（0.2秒〜max_this_time）
                    if max_this_time < 0.2:
                        this_rotation_time = max_this_time
                    else:
                        this_rotation_time = random.uniform(0.2, max_this_time)
                    
                    # 現在位置から動ける範囲をチェック
                    if current_direction_is_cw:
                        available_degrees = self.MAX_ANGLE - self.current_angle - 5  # 5°マージン
                    else:
                        available_degrees = self.current_angle - self.MIN_ANGLE - 5
                    
                    # 回転角度を計算
                    desired_degrees = self.degrees_per_second * this_rotation_time
                    
                    # 範囲制限
                    if available_degrees < 5:
                        print(f"   [{rotation_count}] {'CW' if current_direction_is_cw else 'CCW'}: 範囲端のためスキップ")
                        # 方向を反転して次へ
                        current_direction_is_cw = not current_direction_is_cw
                        continue
                    
                    actual_degrees = min(desired_degrees, available_degrees)
                    actual_time = actual_degrees / self.degrees_per_second
                    
                    print(f"   [{rotation_count}] {'CW' if current_direction_is_cw else 'CCW'}: {actual_degrees:.1f}° ({actual_time:.2f}秒)")
                    
                    # 実際に回転を実行
                    if GPIO_AVAILABLE:
                        GPIOWrapper.output(CW_CCW, ON if current_direction_is_cw else OFF)
                        time.sleep(0.01)
                        GPIOWrapper.output(START_STOP, ON)
                        time.sleep(0.01)
                        GPIOWrapper.output(RUN_BRAKE, ON)
                    
                    # 回転時間だけ待機
                    time.sleep(actual_time)
                    
                    if GPIO_AVAILABLE:
                        GPIOWrapper.output(RUN_BRAKE, OFF)
                        time.sleep(0.01)
                        GPIOWrapper.output(START_STOP, OFF)
                    
                    # 角度位置を更新
                    self._update_angle(current_direction_is_cw, actual_time)
                    
                    # 累計時間を更新
                    total_elapsed += actual_time
                    
                    # 短い停止（次の方向への切り替え）
                    time.sleep(0.05)
                    
                    # 方向を反転
                    current_direction_is_cw = not current_direction_is_cw
                
                print(f"\n✓ 交互ランダム回転完了:")
                print(f"   回転回数: {rotation_count}回")
                print(f"   合計時間: {total_elapsed:.2f}秒")
                print(f"   最終位置: {self.current_angle:.1f}°")
                print()
                return True
                
            except Exception as e:
                print(f"❌ 交互ランダム回転中エラー: {e}")
                # エラー時は停止
                if GPIO_AVAILABLE:
                    GPIOWrapper.output(RUN_BRAKE, OFF)
                    GPIOWrapper.output(START_STOP, OFF)
                return False
