import React from 'react';
import { Mic, MicOff, Volume2 } from 'lucide-react';

const VoiceRecognition = ({ 
  isListening, 
  recognizedText, 
  startListening, 
  stopListening, 
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
          <span className="font-semibold text-gray-700">音声で回答</span>
        </div>
        <button
          onClick={isListening ? stopListening : startListening}
          disabled={disabled}
          className={`px-4 py-2 rounded-lg font-semibold transition flex items-center gap-2 ${
            isListening
              ? 'bg-red-500 text-white hover:bg-red-600'
              : 'bg-blue-500 text-white hover:bg-blue-600'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {isListening ? (
            <>
              <MicOff className="w-4 h-4" />
              停止
            </>
          ) : (
            <>
              <Mic className="w-4 h-4" />
              開始
            </>
          )}
        </button>
      </div>
      
      {isListening && (
        <div className="flex items-center gap-2 text-red-600 animate-pulse">
          <div className="w-3 h-3 bg-red-600 rounded-full"></div>
          <span className="text-sm font-semibold">
            「まる」または「ばつ」と言ってください
          </span>
        </div>
      )}
      
      {recognizedText && (
        <div className="mt-2 text-sm text-gray-600">
          認識: <span className="font-semibold">{recognizedText}</span>
        </div>
      )}
    </div>
  );
};

export default VoiceRecognition;
