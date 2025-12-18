# ○×クイズロボットシステム

## 🚀 セットアップ

### 必要なもの

- Raspberry Pi 5（Ubuntu 24.04 ARM64）
- Node.js 16以上
- Python 3.8以上
- USBカメラ
- マイク
- スピーカー

### 1. Voskモデルのダウンロード

```bash
cd backend
wget https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip
unzip vosk-model-small-ja-0.22.zip
```

### 2. NanoDetモデルの配置

```bash
# model/nanodet_m_320.onnx を配置
mkdir -p backend/model
# モデルファイルを backend/model/ にコピー
```

### 3. バックエンドの起動

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

### 4. フロントエンドの起動

```bash
npm install
npm run dev
```

### 5. 音声ファイルの生成（オプション）

VOICEVOXを起動後:

```bash
python3 generate_quiz_audio.py
```

## 📝 クイズのカスタマイズ

`src/data/quizData.js` を編集:

```javascript
export const quizData = [
  {
    id: 1,
    question: "あなたの問題文",
    answer: true,  // または false
    explanation: "解説文"
  }
];
```

音声ファイルは `public/audio/question_1.wav` として生成してください。

## 🙏 謝辞

- [Vosk](https://alphacephei.com/vosk/) - 軽量音声認識
- [Silero VAD](https://github.com/snakers4/silero-vad) - 音声区間検出
- [NanoDet](https://github.com/RangiLyu/nanodet) - 物体検出
- [VOICEVOX](https://voicevox.hiroshiba.jp/) - 音声合成
