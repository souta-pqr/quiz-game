import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Strict Modeを一時的に無効化（WebSocket接続の問題を回避）
ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
);
