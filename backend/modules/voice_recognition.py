#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vosk + Silero VADによるキーワードスポッティング
"""

import os
import json
import numpy as np
import torch
from typing import Optional
from collections import deque
from vosk import Model, KaldiRecognizer


# グローバル変数
vosk_model = None
vad_model = None
SAMPLE_RATE = 16000


def get_vosk_model():
    """Voskモデルを取得（グローバル変数アクセス用）"""
    return vosk_model


def get_vad_model():
    """VADモデルを取得（グローバル変数アクセス用）"""
    return vad_model


def is_models_ready():
    """モデルが初期化されているか確認"""
    return vosk_model is not None and vad_model is not None


def initialize_vosk():
    """Vosk初期化"""
    global vosk_model
    
    try:
        print("="*60)
        print("Vosk音声認識モデル初期化開始")
        print("="*60)
        
        # modules/ディレクトリの親ディレクトリ（backend/）を基準にする
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(script_dir, 'vosk-model-small-ja-0.22')
        
        print(f"📂 スクリプトディレクトリ: {script_dir}")
        print(f"📂 モデルパス: {model_path}")
        print(f"📂 モデル存在確認: {os.path.exists(model_path)}")
        
        if not os.path.exists(model_path):
            print(f"❌ Voskモデルが見つかりません: {model_path}")
            print("\n以下のコマンドでモデルをダウンロードしてください:")
            print("  cd backend")
            print("  wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip")
            print("  unzip vosk-model-small-ja-0.22.zip")
            return
        
        print(f"⏳ Voskモデル読み込み中...")
        vosk_model = Model(model_path)
        print(f"✅ Vosk小モデルを初期化しました")
        print(f"✅ グローバル変数 vosk_model を設定: {vosk_model is not None}")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Voskモデルの初期化に失敗: {e}")
        import traceback
        traceback.print_exc()


def initialize_vad():
    """VAD初期化"""
    global vad_model
    
    try:
        print("="*60)
        print("Silero VADモデル初期化開始")
        print("="*60)
        
        print("⏳ Silero VADモデルをダウンロード中...")
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        print("✅ Silero VADモデルを初期化しました")
        print(f"✅ グローバル変数 vad_model を設定: {vad_model is not None}")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Silero VADの初期化に失敗: {e}")
        import traceback
        traceback.print_exc()


def detect_answer_keyword(text: str) -> Optional[bool]:
    """キーワード検出
    
    Args:
        text: 認識されたテキスト
        
    Returns:
        True: まる, False: ばつ, None: どちらでもない
    """
    text_lower = text.lower().replace(' ', '')
    
    maru_keywords = [
        'まる', 'マル', '丸', 'まぁる', 'まーる', 'まっる', 'マァル', 'マール', 'マッル',
        'まるる', 'まるん', 'マルル', 'マルン', 'まるっ', 'まるい', 'マルッ', 'マルイ',
        '丸い', '丸っこ', '丸み', 'まぁ', 'まー', 'マァ', 'マー', 'まるまる', 'マルマル', 
        '円', 'まろ', 'まろう', 'マロ', 'マロウ', '丸太', '丸子', 'まある', 'マアル', 'ある',
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
        
        # グローバル変数を直接参照
        if vosk_model is not None:
            self.recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
            self.recognizer.SetWords(True)
            self.recognizer.SetPartialWords(True)
        else:
            self.recognizer = None
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> Optional[dict]:
        """音声チャンク処理"""
        # グローバル変数を直接チェック
        if vad_model is None or self.recognizer is None:
            if vad_model is None:
                print(f"⚠️ VADモデルが未初期化（接続ID: {self.connection_id}）")
            if self.recognizer is None:
                print(f"⚠️ Voskレコグナイザーが未初期化（接続ID: {self.connection_id}）")
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
            # グローバル変数を直接使用
            speech_prob = vad_model(audio_tensor, SAMPLE_RATE).item()
        except Exception as e:
            print(f"❌ VAD処理エラー: {e}")
            return None
        
        is_speech_now = speech_prob > self.vad_threshold
        
        if is_speech_now and not self.is_speech:
            # 音声開始
            print(f"🎤 音声検出開始 (確率: {speech_prob:.3f}, 閾値: {self.vad_threshold})")
            self.is_speech = True
            self.silence_duration = 0
            
            pad_samples = int(SAMPLE_RATE * self.speech_pad_ms / 1000)
            pad_data = list(self.audio_buffer)[-pad_samples:] if len(self.audio_buffer) >= pad_samples else list(self.audio_buffer)
            self.speech_buffer = pad_data + list(chunk)
            
            if self.recognizer:
                self.recognizer.Reset()
            
            # 音声検出開始をクライアントに通知
            return {
                'type': 'speech_status',
                'status': 'speech_started',
                'message': '音声を検出しました'
            }
        
        elif is_speech_now and self.is_speech:
            # 音声継続中
            self.speech_buffer.extend(chunk)
            self.silence_duration = 0
            
            audio_int16 = (np.array(chunk) * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            if self.recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(self.recognizer.Result())
                text = result.get('text', '').strip()
                
                print(f"🗣️ Vosk認識結果（確定）: '{text}'")
                
                if text:
                    answer = detect_answer_keyword(text)
                    print(f"🎯 キーワード判定: テキスト='{text}', 回答={answer}")
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
                    print(f"🗣️ Vosk認識結果（部分）: '{partial_text}'")
                    answer = detect_answer_keyword(partial_text)
                    if answer is not None:
                        print(f"🎯 キーワード判定（部分）: テキスト='{partial_text}', 回答={answer}")
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
            # 無音検出
            self.speech_buffer.extend(chunk)
            self.silence_duration += len(chunk) / SAMPLE_RATE
            
            if self.silence_duration > 0.3:
                duration = len(self.speech_buffer) / SAMPLE_RATE
                
                print(f"🔇 音声終了検出 (無音時間: {self.silence_duration:.2f}s, 音声長: {duration:.2f}s)")
                
                if duration >= self.min_speech_duration:
                    return self._finalize_recognition()
                else:
                    print(f"⚠️ 音声が短すぎるためスキップ (最小: {self.min_speech_duration}s)")
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
            print(f"🎤 音声認識確定処理開始 (バッファサイズ: {len(self.speech_buffer)} サンプル)")
            result = json.loads(self.recognizer.FinalResult())
            text = result.get('text', '').strip()
            
            print(f"🗣️ Vosk最終認識結果: '{text}'")
            
            if text:
                answer = detect_answer_keyword(text)
                print(f"🎯 キーワード判定（最終）: テキスト='{text}', 回答={answer}")
                
                self.is_speech = False
                self.speech_buffer = []
                
                return {
                    'type': 'speech_result',
                    'text': text,
                    'answer': answer,
                    'is_final': True
                }
            else:
                print(f"⚠️ 認識結果が空文字列")
        
        except Exception as e:
            print(f"❌ 認識エラー: {e}")
            import traceback
            traceback.print_exc()
        
        self.is_speech = False
        self.speech_buffer = []
        return None
        
