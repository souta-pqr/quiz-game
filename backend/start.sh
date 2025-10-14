#!/bin/bash

echo "物体検出バックエンドを起動しています..."

cd "$(dirname "$0")"

# 仮想環境のチェック
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
fi

# 仮想環境をアクティブ化
source venv/bin/activate

# 依存関係をインストール
echo "依存関係をインストールしています..."
pip install -r requirements.txt

# サーバーを起動
echo "サーバーを起動しています..."
python server.py
