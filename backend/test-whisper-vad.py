#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper + Silero VAD音声認識のテストスクリプト
マイクからの音声入力をテストし、認識結果を表示します
"""

import os
import sys
import pyaudio
import numpy as np
import torch
import whisper
from collections import deque

def test_whisper_vad():
    """Whisper + VAD音声認識のテスト"""
    print("="*60)
    print("Whisper + Silero VAD音声認識テストスクリプト")
    print("="*60)
    print()
    
    # Whisperモデルを読み込み
    try:
        print("Whisperモデルを読み込み中...")
        model = whisper.load_model("base")
        print("✓ Whisperモデル読み込み成功 (base)")
    except Exception as e:
        print(f"❌ Whisperモデル読み込み失敗: {e}")
        print("pip install openai-whisper を実行してください")
        sys.exit(1)
    
    # Silero VADを読み込み
    try:
        print("Silero VADモデルを読み込み中...")
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        print("✓ Silero VADモデル読み込み成功")
    except Exception as e:
        print(f"❌ Silero VAD読み込み失敗: {e}")
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
    CHUNK = 512  # 32ms @ 16kHz
    
    try:
        stream = p.open(
            format=pyaudio.paFloat32,
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
    
    # VAD設定
    vad_threshold = 0.5
    speech_pad_ms = 300
    min_speech_duration = 0.3
    max_speech_duration = 10.0
    
    # 状態変数
    audio_buffer = deque(maxlen=int(SAMPLE_RATE * 10))
    speech_buffer = []
    is_speech = False
    silence_duration = 0
    
    print("\n" + "="*60)
    print("🎤 音声認識を開始します")
    print("「まる」または「ばつ」と言ってください")
    print("Ctrl+C で終了")
    print("="*60)
    print()
    
    try:
        while True:
            # 音声データを読み取り
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.float32)
            
            # バッファに追加
            audio_buffer.extend(audio_chunk)
            
            # PyTorchテンソルに変換
            audio_tensor = torch.from_numpy(audio_chunk).float()
            
            # VADで音声区間を検出
            try:
                speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
            except Exception as e:
                print(f"VADエラー: {e}")
                continue
            
            is_speech_now = speech_prob > vad_threshold
            
            # 音声区間の開始
            if is_speech_now and not is_speech:
                is_speech = True
                silence_duration = 0
                
                # パディング分のデータを追加
                pad_samples = int(SAMPLE_RATE * speech_pad_ms / 1000)
                pad_data = list(audio_buffer)[-pad_samples:] if len(audio_buffer) >= pad_samples else list(audio_buffer)
                speech_buffer = pad_data + list(audio_chunk)
                
                print(f"🎤 音声開始検出 (信頼度: {speech_prob:.2f})")
            
            # 音声区間の継続
            elif is_speech_now and is_speech:
                speech_buffer.extend(audio_chunk)
                silence_duration = 0
                
                # 最大音声長チェック
                duration = len(speech_buffer) / SAMPLE_RATE
                if duration > max_speech_duration:
                    print(f"⏱️ 最大音声長到達 ({duration:.1f}秒) - 認識開始")
                    
                    # Whisperで認識
                    audio_array = np.array(speech_buffer, dtype=np.float32)
                    
                    # 正規化
                    max_val = np.abs(audio_array).max()
                    if max_val > 0:
                        audio_array = audio_array / max_val
                    
                    print("🔄 Whisper認識中...")
                    result = model.transcribe(
                        audio_array,
                        language='ja',
                        task='transcribe',
                        fp16=False,
                        verbose=False
                    )
                    
                    text = result['text'].strip()
                    if text:
                        print(f"✓ 認識結果: {text}")
                        
                        # 回答判定
                        if any(word in text for word in ['まる', 'マル', '丸', '○']):
                            print("  → ○ まる として認識")
                        elif any(word in text for word in ['ばつ', 'バツ', 'ペケ', '×', 'ばっ']):
                            print("  → × ばつ として認識")
                    else:
                        print("⚠️ 認識結果が空です")
                    
                    # バッファをクリア
                    is_speech = False
                    speech_buffer = []
                    print()
            
            # 音声区間の終了候補
            elif not is_speech_now and is_speech:
                speech_buffer.extend(audio_chunk)
                silence_duration += len(audio_chunk) / SAMPLE_RATE
                
                # 無音が一定時間続いたら音声区間終了
                if silence_duration > 0.5:  # 500ms無音
                    duration = len(speech_buffer) / SAMPLE_RATE
                    
                    if duration >= min_speech_duration:
                        print(f"🔚 音声終了検出 (長さ: {duration:.1f}秒) - 認識開始")
                        
                        # Whisperで認識
                        audio_array = np.array(speech_buffer, dtype=np.float32)
                        
                        # 正規化
                        max_val = np.abs(audio_array).max()
                        if max_val > 0:
                            audio_array = audio_array / max_val
                        
                        print("🔄 Whisper認識中...")
                        result = model.transcribe(
                            audio_array,
                            language='ja',
                            task='transcribe',
                            fp16=False,
                            verbose=False
                        )
                        
                        text = result['text'].strip()
                        if text:
                            print(f"✓ 認識結果: {text}")
                            
                            # 回答判定
                            if any(word in text for word in ['まる', 'マル', '丸', '○']):
                                print("  → ○ まる として認識")
                            elif any(word in text for word in ['ばつ', 'バツ', 'ペケ', '×', 'ばっ']):
                                print("  → × ばつ として認識")
                        else:
                            print("⚠️ 認識結果が空です")
                        
                        # バッファをクリア
                        is_speech = False
                        speech_buffer = []
                        print()
                    else:
                        print(f"⏭️ 音声が短すぎるためスキップ ({duration:.1f}秒)")
                        is_speech = False
                        speech_buffer = []
    
    except KeyboardInterrupt:
        print("\n\n音声認識を停止しています...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("✓ 音声認識を停止しました")

if __name__ == "__main__":
    test_whisper_vad()
    