import React from 'react';
import { Mic, MicOff, Volume2, WifiOff, Trash2, Zap } from 'lucide-react';

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
        <div className="text-xs text-red-600 bg-red-100 p-2 rounded font-mono">
          cd backend && python server.py
        </div>
        {debugInfo && (
          <p className="text-xs text-red-600 font-mono bg-red-100 p-2 rounded mt-2">
            {debugInfo}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-green-50 to-blue-50 p-4 rounded-lg mb-6 border-2 border-green-300 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Volume2 className="w-5 h-5 text-gray-700" />
          <span className="font-semibold text-gray-800">音声認識（常時リスニング）</span>
          {isListening && !disabled && (
            <div className="flex items-center gap-1 ml-2">
              <Zap className="w-4 h-4 text-green-600 animate-pulse" />
              <span className="text-xs text-green-600 font-bold">LIVE</span>
            </div>
          )}
        </div>
        
        {/* リスニング状態インジケーター */}
        <div className="flex items-center gap-2">
          {isListening && !disabled ? (
            <>
              <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-green-100 border border-green-300">
                <Mic className="w-4 h-4 text-green-600" />
                <span className="text-sm font-semibold text-green-700">認識中</span>
              </div>
              {onStop && (
                <button
                  onClick={onStop}
                  className="px-3 py-1 rounded-lg bg-red-100 hover:bg-red-200 transition text-red-700 text-sm font-semibold border border-red-300"
                >
                  <MicOff className="w-4 h-4" />
                </button>
              )}
            </>
          ) : (
            <button
              onClick={onStart}
              disabled={disabled}
              className={`px-3 py-1 rounded-lg transition text-sm font-semibold border ${
                disabled 
                  ? 'bg-gray-300 text-gray-600 border-gray-400 cursor-not-allowed' 
                  : 'bg-blue-500 text-white hover:bg-blue-600 border-blue-600'
              }`}
            >
              <div className="flex items-center gap-2">
                <Mic className="w-4 h-4" />
                再開
              </div>
            </button>
          )}
        </div>
      </div>
      
      {/* リスニングアニメーション */}
      {isListening && !disabled && (
        <div className="flex items-center gap-2 mb-3 bg-white p-3 rounded-lg border border-green-200">
          <div className="flex gap-1">
            <div className="w-1 h-3 bg-green-500 rounded animate-pulse"></div>
            <div className="w-1 h-4 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.1s'}}></div>
            <div className="w-1 h-5 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.2s'}}></div>
            <div className="w-1 h-4 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.3s'}}></div>
            <div className="w-1 h-3 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.4s'}}></div>
          </div>
          <span className="text-sm text-green-700 font-medium">
            「まる」または「ばつ」と言ってください
          </span>
        </div>
      )}
      
      {/* 現在の認識結果表示 */}
      {recognizedText && (
        <div className="mb-3 p-3 bg-white rounded-lg text-sm border-2 border-blue-300 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="text-blue-600 font-semibold">🎤 認識:</span>
            <span className="text-gray-800 font-medium text-lg">{recognizedText}</span>
          </div>
        </div>
      )}
      
      {/* デバッグ情報 */}
      {debugInfo && (
        <div className="mb-3 p-2 bg-gray-100 rounded text-xs font-mono text-gray-600 border border-gray-300">
          🔍 {debugInfo}
        </div>
      )}
      
      {/* 認識履歴 */}
      {recognitionHistory.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-600">📝 認識履歴（最新{recognitionHistory.length}件）</span>
            <button
              onClick={onClearHistory}
              className="text-xs text-gray-500 hover:text-red-600 transition flex items-center gap-1"
            >
              <Trash2 className="w-3 h-3" />
              クリア
            </button>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto bg-white p-2 rounded border border-gray-200">
            {recognitionHistory.slice().reverse().map((item, index) => (
              <div 
                key={index} 
                className={`text-xs p-2 rounded ${
                  item.isFinal 
                    ? item.answer !== null 
                      ? 'bg-green-50 border border-green-300'
                      : 'bg-blue-50 border border-blue-200'
                    : 'bg-gray-50 border border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-gray-800">{item.text}</span>
                  <span className="text-gray-500 text-xs ml-2">{item.timestamp}</span>
                </div>
                {item.answer !== null && (
                  <span className="text-xs font-semibold text-green-700 mt-1 block">
                    → {item.answer ? '○ まる' : '× ばつ'}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* ステータス表示 */}
      {!isListening && recognitionHistory.length === 0 && !disabled && (
        <div className="mt-3 text-xs text-gray-600 bg-white p-3 rounded border border-blue-200">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-500" />
            <div>
              <strong>自動起動:</strong> 音声認識は自動的に開始されます。
              マイクの許可が必要な場合はブラウザから許可してください。
            </div>
          </div>
        </div>
      )}
      
      {disabled && (
        <div className="mt-3 text-xs text-gray-600 bg-yellow-50 p-2 rounded border border-yellow-300">
          ⏸️ 回答処理中のため音声認識を一時停止しています
        </div>
      )}
    </div>
  );
};

export default VoskRecognition;
