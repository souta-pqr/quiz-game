import React, { useEffect } from 'react';
import { Mic, MicOff, Volume2, WifiOff, Trash2, Zap } from 'lucide-react';

/**
 * VoiceRecognition Component（デバッグ版）
 * 音声認識UI（バックエンド: Vosk + Silero VAD）
 */
const VoiceRecognition = ({ 
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
  // コンポーネントマウント時
  useEffect(() => {
    console.log('🎨 VoiceRecognition コンポーネントマウント');
    console.log('  isSupported:', isSupported);
    console.log('  isConnected:', isConnected);
    console.log('  isListening:', isListening);
  }, []);

  // 状態変化をログ
  useEffect(() => {
    console.log('🔄 VoiceRecognition 状態変化:');
    console.log('  isListening:', isListening);
    console.log('  isConnected:', isConnected);
    console.log('  disabled:', disabled);
    console.log('  recognizedText:', recognizedText);
  }, [isListening, isConnected, disabled, recognizedText]);

  if (!isSupported) {
    console.warn('⚠️ マイク非対応');
    return (
      <div className="bg-yellow-50 p-4 rounded-lg mb-6 border border-yellow-200">
        <p className="text-sm text-yellow-800">
          ⚠️ お使いのブラウザはマイク入力に対応していません。手動ボタンで回答してください。
        </p>
      </div>
    );
  }

  if (!isConnected) {
    console.warn('⚠️ WebSocket未接続');
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
          cd backend && python server_with_motor.py
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
    <div className="bg-gradient-to-r from-red-50 via-white to-green-50 p-4 rounded-xl mb-6 border-4 border-red-400 shadow-lg relative">
      {/* クリスマス装飾 */}
      <div className="absolute -top-2 -left-2 text-2xl">🎄</div>
      <div className="absolute -top-2 -right-2 text-2xl">🎅</div>
      
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Volume2 className="w-5 h-5 text-red-700" />
          <span className="font-bold text-red-800">🎤 音声認識 (Vosk)</span>
          {isListening && !disabled && (
            <div className="flex items-center gap-1 ml-2">
              <Zap className="w-4 h-4 text-green-600 animate-pulse" />
              <span className="text-xs text-green-700 font-bold">LIVE</span>
            </div>
          )}
        </div>
        
        {/* リスニング状態インジケーター */}
        <div className="flex items-center gap-2">
          {isListening && !disabled ? (
            <>
              <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-green-100 border-2 border-green-500">
                <Mic className="w-4 h-4 text-green-700" />
                <span className="text-sm font-bold text-green-800">🎄 認識中</span>
              </div>
              {onStop && (
                <button
                  onClick={() => {
                    console.log('🛑 停止ボタンクリック');
                    onStop();
                  }}
                  className="px-3 py-1 rounded-lg bg-red-100 hover:bg-red-200 transition text-red-700 text-sm font-semibold border-2 border-red-400"
                >
                  <MicOff className="w-4 h-4" />
                </button>
              )}
            </>
          ) : (
            <button
              onClick={() => {
                console.log('▶️ 再開ボタンクリック');
                onStart();
              }}
              disabled={disabled}
              className={`px-3 py-1 rounded-lg transition text-sm font-bold border-2 ${
                disabled 
                  ? 'bg-gray-300 text-gray-600 border-gray-400 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-green-500 to-red-500 text-white hover:from-green-600 hover:to-red-600 border-green-600'
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
        <div className="flex items-center justify-center gap-3 mb-3 bg-white p-4 rounded-xl border-2 border-green-400 shadow-md">
          <div className="flex gap-1">
            <div className="w-1.5 h-4 bg-red-500 rounded animate-pulse"></div>
            <div className="w-1.5 h-6 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.1s'}}></div>
            <div className="w-1.5 h-8 bg-red-500 rounded animate-pulse" style={{animationDelay: '0.2s'}}></div>
            <div className="w-1.5 h-6 bg-green-500 rounded animate-pulse" style={{animationDelay: '0.3s'}}></div>
            <div className="w-1.5 h-4 bg-red-500 rounded animate-pulse" style={{animationDelay: '0.4s'}}></div>
          </div>
          <span className="text-base text-gray-800 font-bold">
            「まる」か「ばつ」で回答してください
          </span>
        </div>
      )}
      
      {/* 現在の認識結果表示 */}
      {recognizedText && (
        <div className="mb-3 p-3 bg-white rounded-lg text-sm border-4 border-green-500 shadow-lg">
          <div className="flex items-center gap-2">
            <span className="text-green-700 font-bold">🎤 音声認識 (Vosk):</span>
            <span className="text-gray-800 font-bold text-lg">{recognizedText}</span>
            <span className="text-xl">🎁</span>
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

export default VoiceRecognition;
