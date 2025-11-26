#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超軽量キーワードスポッティングのテストスクリプト
マイクから「まる」「ばつ」を認識してテスト
"""

import os
import sys
import numpy as np
import torch
from vosk import Model, KaldiRecognizer
import json

# PyAudioのインポート（オプション）
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("⚠️ PyAudioがインストールされていません")
    print("pip install pyaudio を実行してください")
    sys.exit(1)

SAMPLE_RATE = 16000

def detect_answer_keyword(text: str):
    """テキストから「まる」「ばつ」を検出"""
    text_lower = text.lower().replace(' ', '')
    
    # 「まる」系
    maru_keywords = ['まる', 'マル', '丸', '○', 'まぁる', 'まーる']
    for keyword in maru_keywords:
        if keyword in text_lower or keyword in text:
            return True
    
    # 「ばつ」系
    batsu_keywords = ['ばつ', 'バツ', 'ペケ', '×', 'ばっ', 'ばっつ']
    for keyword in batsu_keywords:
        if keyword in text_lower or keyword in text:
            return False
    
    return None

def test_keyword_spotting():
    """キーワードスポッティングのテスト"""
    print("="*60)
    print("超軽量キーワードスポッティング テストスクリプト")
    print("="*60)
    print()
    
    # Voskモデルをロード
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, 'vosk-model-small-ja-0.22')
    
    if not os.path.exists(model_path):
        print(f"❌ Voskモデルが見つかりません: {model_path}")
        print()
        print("以下のコマンドでダウンロードしてください:")
        print("  cd backend")
        print("  wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip")
        print("  unzip vosk-model-small-ja-0.22.zip")
        sys.exit(1)
    
    print(f"Voskモデルをロード中: {model_path}")
    try:
        model = Model(model_path)
        print("✓ Voskモデルをロードしました")
    except Exception as e:
        print(f"❌ Voskモデルのロードに失敗: {e}")
        sys.exit(1)
    
    # Silero VADをロード
    print("\nSilero VADをロード中...")
    try:
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        print("✓ Silero VADをロードしました")
    except Exception as e:
        print(f"❌ Silero VADのロードに失敗: {e}")
        sys.exit(1)
    
    # PyAudioを初期化
    print("\nマイクを初期化中...")
    p = pyaudio.PyAudio()
    
    # デフォルトマイクの情報を表示
    default_input = p.get_default_input_device_info()
    print(f"✓ デフォルトマイク: {default_input['name']}")
    
    # 音声ストリームを開く
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=512
    )
    
    print()
    print("="*60)
    print("🎤 キーワードスポッティング開始")
    print("「まる」または「ばつ」と言ってください")
    print("Ctrl+C で終了")
    print("="*60)
    print()
    
    # 認識器を作成
    recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    recognizer.SetWords(True)
    recognizer.SetPartialWords(True)
    
    # VAD設定
    vad_threshold = 0.4
    is_speech = False
    silence_duration = 0
    chunk_duration = 512 / SAMPLE_RATE  # 秒
    
    try:
        while True:
            # 音声データを読み取り
            data = stream.read(512, exception_on_overflow=False)
            audio_int16 = np.frombuffer(data, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0
            
            # VADで音声を検出
            audio_tensor = torch.from_numpy(audio_float).float()
            speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
            
            is_speech_now = speech_prob > vad_threshold
            
            if is_speech_now and not is_speech:
                is_speech = True
                silence_duration = 0
                recognizer.Reset()
                print(f"🎤 音声検出 (信頼度: {speech_prob:.2f})")
            
            elif is_speech_now and is_speech:
                silence_duration = 0
                
                # 認識器にデータを送る
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get('text', '').strip()
                    
                    if text:
                        answer = detect_answer_keyword(text)
                        print(f"✓ 認識: '{text}'", end='')
                        
                        if answer is True:
                            print(" → ○ まる")
                        elif answer is False:
                            print(" → × ばつ")
                        else:
                            print(" → キーワード未検出")
                        
                        is_speech = False
                        recognizer.Reset()
                else:
                    # 部分結果もチェック
                    partial = json.loads(recognizer.PartialResult())
                    partial_text = partial.get('partial', '').strip()
                    
                    if partial_text:
                        answer = detect_answer_keyword(partial_text)
                        if answer is not None:
                            print(f"⚡ 部分認識: '{partial_text}'", end='')
                            
                            if answer is True:
                                print(" → ○ まる [高速検出!]")
                            elif answer is False:
                                print(" → × ばつ [高速検出!]")
                            
                            is_speech = False
                            recognizer.FinalResult()
                            recognizer.Reset()
            
            elif not is_speech_now and is_speech:
                silence_duration += chunk_duration
                
                if silence_duration > 0.3:  # 300ms無音
                    result = json.loads(recognizer.FinalResult())
                    text = result.get('text', '').strip()
                    
                    if text:
                        answer = detect_answer_keyword(text)
                        print(f"✓ 最終認識: '{text}'", end='')
                        
                        if answer is True:
                            print(" → ○ まる")
                        elif answer is False:
                            print(" → × ばつ")
                        else:
                            print(" → キーワード未検出")
                    
                    is_speech = False
                    recognizer.Reset()
    
    except KeyboardInterrupt:
        print("\n\n⏹️ テストを終了しています...")
    
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("✓ テストを終了しました")

if __name__ == "__main__":
    test_keyword_spotting()
