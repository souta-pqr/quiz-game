import React from 'react';
import { Mic, MicOff, Volume2, WifiOff, Trash2 } from 'lucide-react';

const VoskRecognition = ({ 
  isListening, 
  recognizedText, 
  recognitionHistory = [],
  disabled,
  isSupported,
  isConnected,
  debugInfo,
  onStart,
  onStop,
  onClearHistory
}) => {
  if (!isSupported) {
    return (
      <div className="bg-yellow-50 p-4 rounded-lg mb-6 border border-yellow-200">
        <p className="text-sm text-yellow-800">
          ⚠️ お使いのブラウザはマイク入力に対応していません。手動ボタンで回答してください。
        </p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="bg-red-50 p-4 rounded-lg mb-6 border border-red-200">
        <div className="flex items-center gap-2 mb-2">
          <WifiOff className="w-5 h-5 text-red-600" />
          <span className="font-semibold text-red-800">音声認識サーバーに接続できません</span>
        </div>
        <p className="text-sm text-red-700 mb-2">
          バックエンドサーバーが起動しているか確認してください。
        </p>
        {debugInfo && (
          <p className="text-xs text-red-600 font-mono bg-red-100 p-2 rounded">
            {debugInfo}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-green-50 to-blue-50 p-4 rounded-lg mb-6 border border-green-200">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Volume2 className="w-5 h-5 text-gray-700" />
          <span className="font-semibold text-gray-800">音声で回答（Vosk）</span>
        </div>
        
        {/* リスニング状態インジケーター */}
        <div className="flex items-center gap-2">
          {isListening && !disabled ? (
            <>
              <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-green-100">
                <Mic className="w-4 h-4 text-green-600" />
                <span className="text-sm font-semibold text-green-700">リスニング中</span>
              </div>
              <button
                onClick={onStop}
                className="px-3 py-1 rounded-lg bg-red-100 hover:bg-red-200 transition text-red-700 text-sm font-semibold"
              >
                停止
              </button>
            </>
          ) : (
            <button
              onClick={onStart}
              disabled={disabled}
              className={`px-3 py-1 rounded-lg transition text-sm font-semibold ${
                disabled 
                  ? 'bg-gray-300 text-gray-600 cursor-not-allowed' 
                  : 'bg-blue-500 text-white hover:bg-blue-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Mic className="w-4 h-4" />
                開始
              </div>
            </button>
          )}
        </div>
      </div>
      
      {/* リスニングアニメーション */}
      {isListening && !disabled && (
        <div className="flex items-center gap-2 mb-3">
          <div className="flex gap-1">
            <div className="w-1 h-3 bg-green-500 rounded animate-pulse"></div>
            <div className="w-1 h-4 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.1s'}}></div>
            <div className="w-1 h-3 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.2s'}}></div>
          </div>
          <span className="text-sm text-green-700 font-medium">
            「まる」または「ばつ」と言ってください
          </span>
        </div>
      )}
      
      {/* 現在の認識結果表示 */}
      {recognizedText && (
        <div className="mb-3 p-3 bg-white rounded-lg text-sm border border-blue-200 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-blue-600 font-semibold">認識中:</span>
            <span className="text-gray-800 font-medium">{recognizedText}</span>
          </div>
        </div>
      )}
      
      {/* デバッグ情報 */}
      {debugInfo && (
        <div className="mb-3 p-2 bg-gray-100 rounded text-xs font-mono text-gray-700">
          🔍 {debugInfo}
        </div>
      )}
      
      {/* 認識履歴 */}
      {recognitionHistory.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-600">📝 認識履歴</span>
            <button
              onClick={onClearHistory}
              className="text-xs text-gray-500 hover:text-red-600 transition flex items-center gap-1"
            >
              <Trash2 className="w-3 h-3" />
              クリア
            </button>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {recognitionHistory.slice().reverse().map((item, index) => (
              <div 
                key={index} 
                className={`text-xs p-2 rounded ${
                  item.isFinal 
                    ? item.answer !== null 
                      ? 'bg-green-100 border border-green-300'
                      : 'bg-blue-100 border border-blue-300'
                    : 'bg-gray-100 border border-gray-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-gray-800">{item.text}</span>
                  <span className="text-gray-500 text-xs ml-2">{item.timestamp}</span>
                </div>
                {item.answer !== null && (
                  <span className="text-xs font-semibold text-green-700">
                    → {item.answer ? '○ まる' : '× ばつ'}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* 使い方ガイド */}
      {!isListening && recognitionHistory.length === 0 && (
        <div className="mt-3 text-xs text-gray-600 bg-white p-2 rounded border border-gray-200">
          💡 <strong>ヒント:</strong> 「開始」ボタンを押して、はっきりと「まる」または「ばつ」と発話してください
        </div>
      )}
    </div>
  );
};

export default VoskRecognition;
