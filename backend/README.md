## セットアップ

### 1. バックエンドのセットアップ

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. フロントエンドのセットアップ

```bash
npm install
```

## 起動方法

### ターミナル1: バックエンドサーバーを起動

```bash
cd backend
./start.sh
```

または

```bash
cd backend
source venv/bin/activate
python server.py
```

サーバーは `http://localhost:8000` で起動します。

### ターミナル2: フロントエンドを起動

```bash
npm run dev
```

フロントエンドは `http://localhost:5173` で起動します。
