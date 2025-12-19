"""
クイズゲーム用モジュールパッケージ（デバッグ版）
"""

from .gpio_controller import GPIOWrapper, GPIO_AVAILABLE, GPIO_LIBRARY
from .motor_controller import MotorController
from .object_detector_cascade import (
    initialize_detector, 
    run_detection, 
    motor_state, 
    motor_state_lock,
    set_detection_running,
    get_detection_running,
    get_detector,
    is_detector_ready
)

# デバッグ版voice_recognitionをインポート
# 実際のファイル名に応じて調整してください
try:
    from .voice_recognition import initialize_vosk, initialize_vad, FastKeywordSpotter, vosk_model, vad_model
    print("✅ voice_recognitionモジュール読み込み成功")
except ImportError as e:
    print(f"❌ voice_recognitionモジュール読み込み失敗: {e}")
    # ダミーの関数を定義
    def initialize_vosk():
        print("⚠️ initialize_vosk ダミー実装")
    def initialize_vad():
        print("⚠️ initialize_vad ダミー実装")
    class FastKeywordSpotter:
        def __init__(self, connection_id):
            print("⚠️ FastKeywordSpotter ダミー実装")
    vosk_model = None
    vad_model = None

__all__ = [
    'GPIOWrapper',
    'GPIO_AVAILABLE',
    'GPIO_LIBRARY',
    'MotorController',
    'initialize_detector',
    'run_detection',
    'motor_state',
    'motor_state_lock',
    'set_detection_running',
    'get_detection_running',
    'get_detector',
    'is_detector_ready',
    'initialize_vosk',
    'initialize_vad',
    'FastKeywordSpotter',
    'vosk_model',
    'vad_model',
]
