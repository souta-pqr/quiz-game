#!/usr/bin/env python3
import requests
import json
import os
import sys

# 設定
VOICEVOX_HOST = "127.0.0.1"
VOICEVOX_PORT = 50021
SPEAKER = 8  # 春日部つむぎ（聞き取りやすい声）
OUTPUT_DIR = "public/audio"

# クイズデータ（src/data/quizData.js から抽出）
quiz_data = [
    {
        "id": 1,
        "question": "地球は太陽の周りを回っている",
    },
    {
        "id": 2,
        "question": "富士山は日本で2番目に高い山である",
    },
    {
        "id": 3,
        "question": "1週間は7日間である",
    }
]

def generate_audio(text, filename, speaker_id=SPEAKER):
    """テキストから音声ファイルを生成"""
    try:
        # ステップ1: 音声合成クエリの作成
        print(f"クエリ作成中: {text}")
        query_response = requests.post(
            f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/audio_query",
            params={"text": text, "speaker": speaker_id}
        )
        
        if query_response.status_code != 200:
            print(f"✗ クエリ作成失敗: {query_response.status_code}")
            return False
        
        query_data = query_response.json()
        
        # 速度を少し遅くして聞き取りやすく
        query_data['speedScale'] = 0.9
        
        # ステップ2: 音声合成
        print(f"音声合成中...")
        synthesis_response = requests.post(
            f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/synthesis",
            params={"speaker": speaker_id},
            headers={"Content-Type": "application/json"},
            data=json.dumps(query_data)
        )
        
        if synthesis_response.status_code != 200:
            print(f"✗ 音声合成失敗: {synthesis_response.status_code}")
            return False
        
        # ステップ3: ファイル保存
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(synthesis_response.content)
        
        file_size = len(synthesis_response.content)
        print(f"✓ 保存成功: {filepath} ({file_size:,} バイト)")
        return True
        
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False

def main():
    print("="*60)
    print("VOICEVOXクイズ音声ファイル生成スクリプト")
    print("="*60)
    print()
    
    # 出力ディレクトリの作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"出力ディレクトリ: {OUTPUT_DIR}")
    print()
    
    # VOICEVOX Engineの接続確認
    try:
        response = requests.get(f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/speakers")
        if response.status_code != 200:
            print("✗ VOICEVOX Engineに接続できません")
            print("./run を実行してEngineを起動してください")
            sys.exit(1)
        print("✓ VOICEVOX Engine接続確認")
    except Exception as e:
        print(f"✗ VOICEVOX Engineに接続できません: {e}")
        print("./run を実行してEngineを起動してください")
        sys.exit(1)
    
    print()
    print("音声ファイル生成開始...")
    print()
    
    success_count = 0
    
    # 各クイズ問題の音声を生成
    for quiz in quiz_data:
        question_id = quiz['id']
        question_text = quiz['question']
        filename = f"question_{question_id}.wav"
        
        print(f"[{question_id}/{len(quiz_data)}] {question_text}")
        
        if generate_audio(question_text, filename):
            success_count += 1
        
        print()
    
    print("="*60)
    print(f"完了: {success_count}/{len(quiz_data)} ファイル生成成功")
    print("="*60)
    
    if success_count == len(quiz_data):
        print("\n✓ すべての音声ファイルが正常に生成されました！")
    else:
        print(f"\n⚠ {len(quiz_data) - success_count} ファイルの生成に失敗しました")

if __name__ == "__main__":
    main()
    