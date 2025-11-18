import React from 'react';
import { Trophy, RotateCcw, Check, X } from 'lucide-react';

const ResultScreen = ({ score, totalQuestions, answers, onRetry }) => {
  const percentage = Math.round((score / totalQuestions) * 100);

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-700 via-green-700 to-red-800 flex items-center justify-center p-4 relative overflow-hidden">
      {/* クリスマス装飾の背景 */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-10 left-10 text-6xl animate-bounce">🎄</div>
        <div className="absolute top-20 right-20 text-5xl animate-pulse">⛄</div>
        <div className="absolute bottom-20 left-20 text-5xl animate-bounce">🎅</div>
        <div className="absolute bottom-10 right-10 text-6xl animate-pulse">🎁</div>
        <div className="absolute top-1/3 left-1/4 text-4xl animate-pulse">⭐</div>
        <div className="absolute top-2/3 right-1/3 text-4xl animate-bounce">✨</div>
        <div className="absolute top-1/2 left-10 text-3xl animate-pulse">❄️</div>
        <div className="absolute top-1/4 right-10 text-3xl animate-bounce">🔔</div>
      </div>
      
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md w-full relative border-8 border-red-600 z-10" style={{
        backgroundImage: 'linear-gradient(to bottom, #ffffff 0%, #fff5f5 100%)',
        boxShadow: '0 0 60px rgba(255, 0, 0, 0.5), inset 0 0 30px rgba(0, 255, 0, 0.1)'
      }}>
        {/* クリスマス装飾 */}
        <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-7xl">
          🎄
        </div>
        <div className="absolute -top-4 left-8 text-4xl animate-pulse">⭐</div>
        <div className="absolute -top-4 right-8 text-4xl animate-pulse">⭐</div>
        
        <div className="text-center mb-6 mt-6">
          <Trophy className="w-24 h-24 text-yellow-400 mx-auto mb-4 animate-pulse" style={{
            filter: 'drop-shadow(0 0 10px rgba(255, 215, 0, 0.8))'
          }} />
          <h2 className="text-4xl font-bold text-red-700 mb-2 flex items-center justify-center gap-2">
            🎅 クイズ終了! 🎄
          </h2>
          <div className="text-7xl font-bold bg-gradient-to-r from-red-600 to-green-600 bg-clip-text text-transparent my-4">
            {score} / {totalQuestions}
          </div>
          <p className="text-2xl font-bold text-gray-700">
            🎁 正答率: {percentage}% 🎁
          </p>
        </div>

        <div className="space-y-3 mb-6 max-h-64 overflow-y-auto">
          {answers.map((answer, index) => (
            <div 
              key={index} 
              className={`p-3 rounded-lg border-2 ${
                answer.isCorrect 
                  ? 'bg-green-50 border-green-400' 
                  : 'bg-red-50 border-red-400'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-800 flex-1 font-medium">
                  {answer.isCorrect ? '🎄' : '⛄'} 問{index + 1}: {answer.question}
                </span>
                {answer.isCorrect ? (
                  <Check className="w-6 h-6 text-green-700 flex-shrink-0" />
                ) : (
                  <X className="w-6 h-6 text-red-700 flex-shrink-0" />
                )}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={onRetry}
          className="w-full bg-gradient-to-r from-red-600 to-green-600 text-white py-4 rounded-xl font-bold text-lg hover:from-red-700 hover:to-green-700 transition flex items-center justify-center gap-2 shadow-lg hover:shadow-xl border-4 border-yellow-300"
          style={{ textShadow: '2px 2px 4px rgba(0,0,0,0.3)' }}
        >
          <RotateCcw className="w-6 h-6" />
          🎅 もう一度挑戦 🎄
        </button>
        
        {/* クリスマス装飾 - フッター */}
        <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 text-5xl">
          🎁
        </div>
        <div className="absolute -bottom-3 left-6 text-3xl">🔔</div>
        <div className="absolute -bottom-3 right-6 text-3xl">🔔</div>
      </div>
    </div>
  );
};

export default ResultScreen;
