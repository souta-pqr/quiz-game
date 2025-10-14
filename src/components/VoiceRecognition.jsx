import React from 'react';
import { Mic, Volume2 } from 'lucide-react';

const VoiceRecognition = ({ 
  isListening, 
  recognizedText, 
  disabled,
  isSupported 
}) => {
  if (!isSupported) {
    return (
      <div className="bg-yellow-50 p-4 rounded-lg mb-6">
        <p className="text-sm text-yellow-800">
          お使いのブラウザは音声認識に対応していません。手動ボタンで回答してください。
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 p-4 rounded-lg mb-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Volume2 className="w-5 h-5 text-gray-600" />
          <span className="font-semibold text-gray-700">音声で回答（常時リスニング中）</span>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1 rounded-lg ${
          disabled ? 'bg-gray-300' : 'bg-green-100'
        }`}>
          <Mic className={`w-4 h-4 ${disabled ? 'text-gray-500' : 'text-green-600'}`} />
          <span className={`text-sm font-semibold ${
            disabled ? 'text-gray-600' : 'text-green-700'
          }`}>
            {disabled ? '一時停止中' : 'リスニング中'}
          </span>
        </div>
      </div>
      
      {isListening && !disabled && (
        <div className="flex items-center gap-2 mb-2">
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
      
      {recognizedText && (
        <div className="mt-2 p-2 bg-blue-50 rounded text-sm text-gray-700 border border-blue-200">
          認識中: <span className="font-semibold text-blue-700">{recognizedText}</span>
        </div>
      )}
    </div>
  );
};

export default VoiceRecognition;
