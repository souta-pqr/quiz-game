#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
クイズゲーム用モーター制御統合サーバー (Raspberry Pi 5対応版)
回答者再選択機能追加: 回答終了後、モーターをランダムに動かして新しい回答者を選ぶ
"""

import asyncio
import cv2
import json
import time
import os
import numpy as np
import torch
import base64
import random
from typing import Set, Optional, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from vosk import Model, KaldiRecognizer
import threading

# GPIO制御のインポート（Raspberry Pi 5対応）
GPIO_AVAILABLE = False
GPIO_LIBRARY = None

# まずrpi-lgpioを試す（Raspberry Pi 5推奨）
try:
    import RPi.GPIO as GPIO
    # Raspberry Pi 5チェック
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO_AVAILABLE = True
        GPIO_LIBRARY = "RPi.GPIO"
        print("✓ RPi.GPIOを使用します")
    except Exception as e:
        if "SOC peripheral" in str(e):
            # Raspberry Pi 5エラー - lgpioに切り替え
            print(f"⚠️ RPi.GPIOはRaspberry Pi 5で動作しません: {e}")
            GPIO_AVAILABLE = False
        else:
            raise
except ImportError:
    print("⚠️ RPi.GPIOがインポートできません")

# RPi.GPIOが使えない場合、lgpioを試す
if not GPIO_AVAILABLE:
    try:
        import lgpio
        GPIO_AVAILABLE = True
        GPIO_LIBRARY = "lgpio"
        print("✓ lgpioライブラリを使用します (Raspberry Pi 5対応)")
    except ImportError:
        print("⚠️ lgpioが利用できません。ダミーモードで動作します。")
        print("  インストール: pip install rpi-lgpio")

# ===================================
# GPIO設定
# ===================================
START_STOP = 24
RUN_BRAKE = 12
CW_CCW = 14
INT_VR_EXT = 1

ON = 0
OFF = 1

# lgpio用のハンドル
lgpio_handle = None

# ===================================
# GPIO抽象化レイヤー
# ===================================
class GPIOWrapper:
    """GPIO操作の抽象化クラス"""
    
    @staticmethod
    def setup_pins():
        """GPIOピンのセットアップ"""
        global lgpio_handle
        
        if not GPIO_AVAILABLE:
            return True
        
        if GPIO_LIBRARY == "RPi.GPIO":
            try:
                GPIO.setup(START_STOP, GPIO.OUT)
                GPIO.setup(RUN_BRAKE, GPIO.OUT)
                GPIO.setup(CW_CCW, GPIO.OUT)
                GPIO.setup(INT_VR_EXT, GPIO.OUT)
                print("✓ RPi.GPIO ピンセットアップ完了")
                return True
            except Exception as e:
                print(f"❌ RPi.GPIO セットアップエラー: {e}")
                return False
        
        elif GPIO_LIBRARY == "lgpio":
            try:
                # gpiochip4 を開く（Raspberry Pi 5）
                lgpio_handle = lgpio.gpiochip_open(4)
                
                # 出力として設定
                lgpio.gpio_claim_output(lgpio_handle, START_STOP)
                lgpio.gpio_claim_output(lgpio_handle, RUN_BRAKE)
                lgpio.gpio_claim_output(lgpio_handle, CW_CCW)
                lgpio.gpio_claim_output(lgpio_handle, INT_VR_EXT)
                
                print("✓ lgpio ピンセットアップ完了 (gpiochip4)")
                return True
            except Exception as e:
                print(f"❌ lgpio セットアップエラー: {e}")
                # gpiochip0を試す
                try:
                    lgpio_handle = lgpio.gpiochip_open(0)
                    lgpio.gpio_claim_output(lgpio_handle, START_STOP)
                    lgpio.gpio_claim_output(lgpio_handle, RUN_BRAKE)
                    lgpio.gpio_claim_output(lgpio_handle, CW_CCW)
                    lgpio.gpio_claim_output(lgpio_handle, INT_VR_EXT)
                    print("✓ lgpio ピンセットアップ完了 (gpiochip0)")
                    return True
                except Exception as e2:
                    print(f"❌ lgpio (gpiochip0) セットアップエラー: {e2}")
                    return False
        
        return False
    
    @staticmethod
    def output(pin, value):
        """GPIO出力"""
        if not GPIO_AVAILABLE:
            return
        
        if GPIO_LIBRARY == "RPi.GPIO":
            GPIO.output(pin, GPIO.LOW if value == ON else GPIO.HIGH)
        
        elif GPIO_LIBRARY == "lgpio":
            if lgpio_handle is not None:
                lgpio.gpio_write(lgpio_handle, pin, value)
    
    @staticmethod
    def cleanup():
        """GPIOクリーンアップ"""
        global lgpio_handle
        
        if not GPIO_AVAILABLE:
            return
        
        if GPIO_LIBRARY == "RPi.GPIO":
            try:
                GPIO.cleanup()
                print("✓ RPi.GPIO クリーンアップ完了")
            except:
                pass
        
        elif GPIO_LIBRARY == "lgpio":
            if lgpio_handle is not None:
                try:
                    lgpio.gpiochip_close(lgpio_handle)
                    lgpio_handle = None
                    print("✓ lgpio クリーンアップ完了")
                except:
                    pass

# ===================================
# モーター設定
# ===================================
HALF_ROTATION_TIME = 0.9  # 半回転（180°）にかかる時間
STEP_DURATION = 0.15
STEP_PAUSE = 0.50

# グローバル変数
active_connections: Set[WebSocket] = set()
detector = None
detection_running = False
motor_controller = None
vosk_model = None
vad_model = None
SAMPLE_RATE = 16000
audio_buffers = {}

# モーター状態管理
motor_state = {
    "is_running": False,
    "is_stopped_for_answer": False,
    "snapshot_image": None,
    "detection_timestamp": None
}
motor_state_lock = threading.RLock()


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
        
        # 🆕 位置追跡（角度: -90° 〜 +90°）
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
            
            # 🆕 角度位置を更新
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
    
    # 🆕 ランダム回転機能（回答者再選択用） - 交互動作版
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


def initialize_vosk():
    """Vosk初期化"""
    global vosk_model
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(script_dir, 'vosk-model-small-ja-0.22')
        
        if not os.path.exists(model_path):
            print(f"⚠️ Voskモデルが見つかりません")
            return
        
        print(f"Voskモデルを初期化中...")
        vosk_model = Model(model_path)
        print(f"✓ Vosk小モデルを初期化しました")
        
    except Exception as e:
        print(f"✗ Voskモデルの初期化に失敗: {e}")

def initialize_vad():
    """VAD初期化"""
    global vad_model
    
    try:
        print("Silero VADモデルを初期化中...")
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        print("✓ Silero VADモデルを初期化しました")
        
    except Exception as e:
        print(f"⚠️ Silero VADの初期化に失敗: {e}")

def detect_answer_keyword(text: str) -> Optional[bool]:
    """キーワード検出"""
    text_lower = text.lower().replace(' ', '')
    
    maru_keywords = [
        'まる', 'マル', '丸', 'まぁる', 'まーる', 'まっる', 'マァル', 'マール', 'マッル',
        'まるる', 'まるん', 'マルル', 'マルン', 'まるっ', 'まるい', 'マルッ', 'マルイ',
        '丸い', '丸っこ', '丸み', 'まぁ', 'まー', 'マァ', 'マー', 'まるまる', 'マルマル', 
        '丸丸', '円', 'まろ', 'まろう', 'マロ', 'マロウ', '丸太', '丸子', 'まある', 'マアル', 'ある',
    ]
    for keyword in maru_keywords:
        if keyword in text_lower or keyword in text:
            return True
    
    batsu_keywords = [
        'ばつ', 'バツ', '罰', 'ばっ', 'ばー', 'バッ', 'バー', 'ばっつ', 'ばーつ', 'バッツ', 
        'バーツ', 'ぺけ', 'ペケ', 'ぺっけ', 'ペッケ', 'ばつばつ', 'バツバツ', '月', 'つき', 
        'ツキ', 'はつ', 'ハツ', '初', '八', 'ぱつ', 'パツ', 'がつ',
    ]
    for keyword in batsu_keywords:
        if keyword in text_lower or keyword in text:
            return False
    
    return None

class FastKeywordSpotter:
    """高速キーワードスポッティング"""
    
    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.sample_rate = SAMPLE_RATE
        self.audio_buffer = deque(maxlen=int(SAMPLE_RATE * 10))
        self.speech_buffer = []
        self.is_speech = False
        self.silence_duration = 0
        
        self.vad_threshold = 0.4
        self.speech_pad_ms = 200
        self.min_speech_duration = 0.25
        self.max_speech_duration = 3.0
        self.vad_chunk_size = 512
        self.pending_samples = np.array([], dtype=np.float32)
        
        if vosk_model is not None:
            self.recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            self.recognizer.SetWords(True)
            self.recognizer.SetPartialWords(True)
        else:
            self.recognizer = None
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> Optional[dict]:
        """音声チャンク処理"""
        if vad_model is None or self.recognizer is None:
            return None
        
        self.audio_buffer.extend(audio_data)
        
        combined_data = np.concatenate([self.pending_samples, audio_data])
        num_full_chunks = len(combined_data) // self.vad_chunk_size
        
        for i in range(num_full_chunks):
            start_idx = i * self.vad_chunk_size
            end_idx = start_idx + self.vad_chunk_size
            chunk = combined_data[start_idx:end_idx]
            
            result = self._process_vad_chunk(chunk)
            if result:
                return result
        
        remaining_start = num_full_chunks * self.vad_chunk_size
        self.pending_samples = combined_data[remaining_start:]
        
        return None
    
    def _process_vad_chunk(self, chunk: np.ndarray) -> Optional[dict]:
        """VADチャンク処理"""
        audio_tensor = torch.from_numpy(chunk).float()
        
        try:
            speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
        except Exception as e:
            return None
        
        is_speech_now = speech_prob > self.vad_threshold
        
        if is_speech_now and not self.is_speech:
            self.is_speech = True
            self.silence_duration = 0
            
            pad_samples = int(SAMPLE_RATE * self.speech_pad_ms / 1000)
            pad_data = list(self.audio_buffer)[-pad_samples:] if len(self.audio_buffer) >= pad_samples else list(self.audio_buffer)
            self.speech_buffer = pad_data + list(chunk)
            
            if self.recognizer:
                self.recognizer.Reset()
        
        elif is_speech_now and self.is_speech:
            self.speech_buffer.extend(chunk)
            self.silence_duration = 0
            
            audio_int16 = (np.array(chunk) * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            if self.recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                
                if text:
                    answer = detect_answer_keyword(text)
                    if answer is not None:
                        self.is_speech = False
                        self.speech_buffer = []
                        
                        return {
                            'type': 'speech_result',
                            'text': text,
                            'answer': answer,
                            'is_final': True
                        }
            else:
                partial_result = json.loads(self.recognizer.PartialResult())
                partial_text = partial_result.get('partial', '').strip()
                
                if partial_text:
                    answer = detect_answer_keyword(partial_text)
                    if answer is not None:
                        self.is_speech = False
                        self.speech_buffer = []
                        
                        final_result = json.loads(self.recognizer.FinalResult())
                        
                        return {
                            'type': 'speech_result',
                            'text': partial_text,
                            'answer': answer,
                            'is_final': True
                        }
            
            duration = len(self.speech_buffer) / SAMPLE_RATE
            if duration > self.max_speech_duration:
                return self._finalize_recognition()
        
        elif not is_speech_now and self.is_speech:
            self.speech_buffer.extend(chunk)
            self.silence_duration += len(chunk) / SAMPLE_RATE
            
            if self.silence_duration > 0.3:
                duration = len(self.speech_buffer) / SAMPLE_RATE
                
                if duration >= self.min_speech_duration:
                    return self._finalize_recognition()
                else:
                    self.is_speech = False
                    self.speech_buffer = []
        
        return None
    
    def _finalize_recognition(self) -> Optional[dict]:
        """認識確定"""
        if not self.speech_buffer or self.recognizer is None:
            self.is_speech = False
            self.speech_buffer = []
            return None
        
        try:
            result = json.loads(self.recognizer.FinalResult())
            text = result.get('text', '').strip()
            
            if text:
                answer = detect_answer_keyword(text)
                
                self.is_speech = False
                self.speech_buffer = []
                
                return {
                    'type': 'speech_result',
                    'text': text,
                    'answer': answer,
                    'is_final': True
                }
        
        except Exception as e:
            print(f"❌ 認識エラー: {e}")
        
        self.is_speech = False
        self.speech_buffer = []
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ライフサイクル管理"""
    initialize_detector()
    initialize_vad()
    initialize_vosk()
    initialize_motor()
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
        if not GPIOWrapper.setup_pins():
            print("❌ GPIOピンのセットアップに失敗しました")
    
    motor_controller = MotorController()
    
    try:
        motor_controller.initialize()
    except Exception as e:
        print(f"⚠️ モーター初期化に失敗しましたが、続行します: {e}")

def cleanup_motor():
    """モータークリーンアップ"""
    global motor_controller
    
    if motor_controller:
        try:
            motor_controller.normal_stop()
        except:
            pass
    
    GPIOWrapper.cleanup()

def initialize_detector():
    """物体検出初期化"""
    global detector
    
    try:
        from nanodet import NanoDetONNX
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
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

async def broadcast_message(message: dict):
    """全クライアントにメッセージ送信"""
    disconnected = set()
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            disconnected.add(connection)
    
    active_connections.difference_update(disconnected)

async def run_detection():
    """物体検出ループ（モーター制御統合版）"""
    global detection_running, motor_state
    
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
                        await broadcast_message({
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

@app.get("/")
async def root():
    return {
        "message": "クイズゲーム用モーター制御統合サーバー（回答者再選択機能付き）",
        "websocket_endpoints": {
            "detection": "/ws/detection",
            "speech": "/ws/speech"
        },
        "gpio_library": GPIO_LIBRARY if GPIO_AVAILABLE else "dummy",
        "motor_ready": motor_controller is not None and motor_controller.is_initialized,
        "vosk_ready": vosk_model is not None,
        "vad_ready": vad_model is not None,
        "detector_ready": detector is not None,
        "features": [
            "位置追跡（-90° 〜 +90°）",
            "回答者再選択（ランダム回転）",
            "ケーブル巻き込み防止"
        ]
    }

@app.get("/status")
async def status():
    with motor_state_lock:
        motor_angle = motor_controller.current_angle if motor_controller else 0.0
        return {
            "detection_running": detection_running,
            "active_connections": len(active_connections),
            "motor_running": motor_state["is_running"],
            "motor_stopped_for_answer": motor_state["is_stopped_for_answer"],
            "motor_angle": f"{motor_angle:.1f}°",
            "vosk_model_loaded": vosk_model is not None,
            "vad_model_loaded": vad_model is not None,
            "detector_loaded": detector is not None,
            "motor_initialized": motor_controller is not None and motor_controller.is_initialized,
            "gpio_library": GPIO_LIBRARY if GPIO_AVAILABLE else "dummy"
        }

@app.post("/motor/resume")
async def resume_motor():
    """モーター再開API（解説終了後に呼ばれる）
    
    🆕 回答者再選択機能（交互ランダム回転版）:
    1. 「モーター処理中」をクライアントに通知
    2. CWとCCWを交互にランダムに回転（合計2〜3秒、各最大0.7秒）
    3. 3秒待機（同じ人の再検出を避ける）
    4. 処理完了をクライアントに通知
    5. 通常の回転を再開
    """
    global motor_state
    
    with motor_state_lock:
        if motor_state["is_stopped_for_answer"]:
            print("\n" + "="*60)
            print("🔄 モーター再開リクエスト受信")
            print("="*60)
            
            # ステップ0: モーター処理中を通知
            print("\n【ステップ0】クライアントに処理開始を通知")
            await broadcast_message({
                "type": "motor_processing",
                "message": "次の回答者を選んでいます...",
                "status": "started"
            })
            await asyncio.sleep(0.5)  # 画面表示のため少し待機
            
            # ステップ1: 交互ランダム回転で回答者を再選択
            print("\n【ステップ1】回答者再選択のため交互ランダム回転")
            if motor_controller and motor_controller.is_initialized:
                success = motor_controller.perform_random_rotation_for_reselection()
                if not success:
                    print("⚠️ 交互ランダム回転に失敗しましたが、続行します")
            
            # ステップ2: 待機（同じ人の再検出を避ける）
            print("\n【ステップ2】待機中（3秒）...")
            await asyncio.sleep(3.0)
            
            # ステップ3: 回答待ち状態を解除
            motor_state["is_stopped_for_answer"] = False
            motor_state["snapshot_image"] = None
            motor_state["detection_timestamp"] = None
            
            # ステップ4: 処理完了を通知
            print("\n【ステップ3】クライアントに処理完了を通知")
            await broadcast_message({
                "type": "motor_processing",
                "message": "処理完了",
                "status": "completed"
            })
            await asyncio.sleep(0.5)  # 画面を閉じるための時間
            
            # ステップ5: 通常の回転を再開
            print("\n【ステップ4】通常回転を再開")
            if not motor_controller.is_running and motor_controller.is_initialized:
                motor_controller.get_next_rotation_direction()
                motor_controller.start_slow_rotation()
                motor_state["is_running"] = True
                print("✓ モーター再開完了")
            
            print("="*60)
            print()
            
            return {"status": "resumed", "message": "回答者再選択完了（交互ランダム回転）"}
        else:
            return {"status": "not_stopped", "message": "回答待ち状態ではありません"}

@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    global detection_running
    
    await websocket.accept()
    active_connections.add(websocket)
    
    if detector is not None and motor_controller is not None and motor_controller.is_initialized and not detection_running:
        detection_running = True
        
        # モーター初回起動
        await asyncio.sleep(2)
        motor_controller.start_slow_rotation()
        with motor_state_lock:
            motor_state["is_running"] = True
        
        asyncio.create_task(run_detection())
    
    try:
        while True:
            data = await websocket.receive()
            
            if "text" in data:
                message = json.loads(data["text"])
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        
        if len(active_connections) == 0:
            detection_running = False
    except Exception as e:
        print(f"物体検出WebSocketエラー: {e}")
        active_connections.discard(websocket)

@app.websocket("/ws/speech")
async def websocket_speech(websocket: WebSocket):
    await websocket.accept()
    connection_id = str(id(websocket))
    
    spotter = FastKeywordSpotter(connection_id)
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
                    
                    if vosk_model is not None and vad_model is not None:
                        try:
                            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
                            audio_float = audio_np.astype(np.float32) / 32768.0
                            
                            result = spotter.process_audio_chunk(audio_float)
                            
                            if result:
                                await websocket.send_json(result)
                        
                        except Exception as e:
                            print(f"❌ 音声処理エラー: {e}")
                
                elif "type" in message and message["type"] == "websocket.disconnect":
                    break
            
            except Exception as e:
                if "disconnect" in str(e).lower():
                    break
                else:
                    print(f"❌ メッセージ受信エラー: {e}")
                    break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"音声認識WebSocketエラー: {e}")
    finally:
        if connection_id in audio_buffers:
            del audio_buffers[connection_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
