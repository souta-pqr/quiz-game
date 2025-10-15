# ○×クイズゲーム

音声認識と物体検出機能を統合したインタラクティブな○×クイズゲームです。

## 🚀 セットアップ

### 前提条件

- Node.js (v16以上)
- Python 3.8以上
- カメラデバイス
- Chrome/Edge（音声認識対応ブラウザ）

### 1. フロントエンドのセットアップ

```bash
# 依存関係をインストール
npm install

# 開発サーバーを起動
npm run dev
```

フロントエンドは `http://localhost:5173` で起動します。

### 2. バックエンドのセットアップ

```bash
# バックエンドディレクトリに移動
cd backend

# Python仮想環境を作成
python3 -m venv venv

# 仮想環境をアクティブ化
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# 依存関係をインストール
pip install -r requirements.txt

# サーバーを起動
python server.py
```

バックエンドは `http://localhost:8000` で起動します。

## 📖 使い方

1. バックエンドとフロントエンドの両方を起動
2. ブラウザで `http://localhost:5173` にアクセス
3. カメラの前に立つ
4. 物体検出が「人」を検出すると、画面に表示される
5. 3秒後、自動的に問題の音声が再生される
6. 音声で「まる」「ばつ」と答えるか、ボタンをクリック
7. 全問終了後、結果画面が表示される

## 🎮 操作方法

### 音声で回答
- 音声認識は常時有効
- 「まる」または「ばつ」と発声すると自動的に回答

### ボタンで回答
- 「○まる」または「×ばつ」ボタンをクリック

### 物体検出による自動再生
- カメラの前に立つと人を検出
- 3秒間検出し続けると自動的に音声が再生される

## 🛠️ カスタマイズ

### クイズ内容の変更

`src/data/quizData.js` を編集：

```javascript
export const quizData = [
  {
    id: 1,
    question: "問題文",
    answer: true,  // または false
    explanation: "解説文"
  },
  // 問題を追加...
];
```

### 音声ファイルの生成

VOICEVOXを使用して音声ファイルを生成：

```bash
# VOICEVOXを起動後
python3 generate_quiz_audio.py
```

## 🔧 技術スタック

### フロントエンド
- **React 18** - UIフレームワーク
- **Vite** - ビルドツール
- **Tailwind CSS** - スタイリング
- **Web Speech API** - 音声認識
- **WebSocket** - リアルタイム通信
- **Lucide React** - アイコン

### バックエンド
- **FastAPI** - Webフレームワーク
- **OpenCV** - 画像処理
- **ONNX Runtime** - 物体検出
- **NanoDet** - 物体検出モデル
- **WebSocket** - リアルタイム通信

## 🌐 ブラウザサポート

- **Google Chrome** (推奨)
- **Microsoft Edge**
- **Safari** (iOS 14.5以降)

※ Firefoxでは音声認識機能が利用できませんが、手動ボタンで回答できます。

## 🙏 謝辞

- [NanoDet](https://github.com/RangiLyu/nanodet) - 物体検出モデル
- [VOICEVOX](https://voicevox.hiroshiba.jp/) - 音声合成エンジン
