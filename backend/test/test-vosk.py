#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vosk音声認識のテストスクリプト
マイクからの音声入力をテストし、認識結果を表示します
"""

import os
import sys
import pyaudio
import json
from vosk import Model, KaldiRecognizer

def test_vosk():
    """Vosk音声認識のテスト"""
    print("="*60)
    print("Vosk音声認識テストスクリプト")
    print("="*60)
    print()
    
    # モデルパスの検索
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_paths = [
        os.path.join(script_dir, 'model', 'vosk-model-small-ja-0.22'),
        os.path.join(script_dir, 'vosk-model-small-ja-0.22'),
    ]
    
    model_path = None
    for path in model_paths:
        if os.path.exists(path):
            model_path = path
            break
    
    if model_path is None:
        print("❌ Voskモデルが見つかりません")
        print("\n以下のコマンドでモデルをダウンロードしてください:")
        print("wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip")
        print("unzip vosk-model-small-ja-0.22.zip")
        print("mkdir -p model && mv vosk-model-small-ja-0.22 model/")
        sys.exit(1)
    
    print(f"✓ Voskモデルを発見: {model_path}")
    
    # モデルを読み込み
    try:
        print("モデルを読み込み中...")
        model = Model(model_path)
        print("✓ モデル読み込み成功")
    except Exception as e:
        print(f"❌ モデル読み込み失敗: {e}")
        sys.exit(1)
    
    # PyAudioの初期化
    print("\nマイクの初期化中...")
    try:
        p = pyaudio.PyAudio()
        print("✓ PyAudio初期化成功")
    except Exception as e:
        print(f"❌ PyAudio初期化失敗: {e}")
        print("pip install pyaudio を実行してください")
        sys.exit(1)
    
    # マイクデバイスの情報を表示
    print("\n利用可能なマイクデバイス:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"  [{i}] {info['name']} (入力チャンネル: {info['maxInputChannels']})")
    
    # デフォルトデバイスを使用
    device_info = p.get_default_input_device_info()
    print(f"\n✓ デフォルトマイク: {device_info['name']}")
    
    # 音声ストリームを開く
    SAMPLE_RATE = 16000
    CHUNK = 4096
    
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        print(f"✓ 音声ストリーム開始 (サンプルレート: {SAMPLE_RATE}Hz)")
    except Exception as e:
        print(f"❌ 音声ストリーム開始失敗: {e}")
        p.terminate()
        sys.exit(1)
    
    # KaldiRecognizerの初期化
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(True)
    
    print("\n" + "="*60)
    print("🎤 音声認識を開始します")
    print("「まる」または「ばつ」と言ってください")
    print("Ctrl+C で終了")
    print("="*60)
    print()
    
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get('text'):
                    text = result['text']
                    print(f"✓ 完全認識: {text}")
                    
                    # 回答判定
                    if "まる" in text or "マル" in text or "丸" in text:
                        print("  → ○ まる として認識")
                    elif "ばつ" in text or "バツ" in text or "ペケ" in text:
                        print("  → × ばつ として認識")
            else:
                partial = json.loads(rec.PartialResult())
                if partial.get('partial'):
                    print(f"⋯ 部分認識: {partial['partial']}", end='\r')
    
    except KeyboardInterrupt:
        print("\n\n音声認識を停止しています...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("✓ 音声認識を停止しました")

if __name__ == "__main__":
    test_vosk()
    