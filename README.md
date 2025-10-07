# ○×クイズゲーム

音声認識機能付きのインタラクティブな○×クイズゲームです。

### 前提条件

- Node.js (v16以上)
- npm または yarn

### インストール

1. 依存関係をインストール

```bash
npm install
```

2. 開発サーバーを起動

```bash
npm run dev
```

3. ブラウザで http://localhost:3000 を開く

### ビルド

本番用ビルドを作成:

```bash
npm run build
```

ビルドをプレビュー:

```bash
npm run preview
```

## 使い方

1. **音声で回答する場合**:
   - 「音声で回答」セクションの「開始」ボタンをクリック
   - 「まる」または「ばつ」と発声
   - 自動的に回答が送信されます

2. **ボタンで回答する場合**:
   - 「○まる」または「×ばつ」ボタンをクリック

3. 全3問終了後、結果画面が表示されます
4. 「もう一度挑戦」ボタンでリトライ可能

## クイズのカスタマイズ

`src/data/quizData.js` ファイルを編集することで、クイズ内容を変更できます:

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

## 技術スタック

- **React 18** - UIフレームワーク
- **Vite** - ビルドツール
- **Tailwind CSS** - スタイリング
- **Web Speech API** - 音声認識
- **Lucide React** - アイコン

## ブラウザサポート

音声認識機能は以下のブラウザで動作します:

- Google Chrome (推奨)
- Microsoft Edge
- Safari (iOS 14.5以降)

※ Firefoxでは音声認識機能が利用できませんが、手動ボタンで回答できます。
