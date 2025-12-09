import React from 'react';
import { RotateCcw } from 'lucide-react';

const ResultScreen = ({ score, totalQuestions, answers = [], onRetry }) => {
  const percentage = totalQuestions > 0 ? Math.round((score / totalQuestions) * 100) : 0;
  
  // 評価メッセージを決定
  let message = '🎄 よく頑張りました！';
  let emoji = '⛄';
  
  if (percentage === 100) {
    message = '🎅 完璧です！素晴らしい！';
    emoji = '🎉';
  } else if (percentage >= 80) {
    message = '⭐ とても良くできました！';
    emoji = '✨';
  } else if (percentage >= 60) {
    message = '🎄 よく頑張りました！';
    emoji = '🎄';
  } else {
    message = '⛄ もう一度挑戦してみましょう！';
    emoji = '💪';
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-700 via-green-700 to-red-800 flex items-center justify-center p-4 relative overflow-hidden">
      {/* シンプルな背景装飾 */}
      <div className="absolute inset-0 pointer-events-none opacity-30">
        <div className="absolute top-10 left-10 text-6xl">🎄</div>
        <div className="absolute top-20 right-20 text-5xl">⛄</div>
        <div className="absolute bottom-20 left-20 text-5xl">🎅</div>
        <div className="absolute bottom-10 right-10 text-6xl">🎁</div>
      </div>
      
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-lg w-full relative border-8 border-red-600 z-10">
        {/* ヘッダー装飾 */}
        <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-7xl">
          🎄
        </div>
        
        <div className="text-center mb-8 mt-8">
          {/* 結果表示 */}
          <div className="text-8xl mb-6">{emoji}</div>
          <h2 className="text-3xl font-bold text-red-700 mb-4">
            クイズ終了！
          </h2>
          <div className="bg-gradient-to-r from-red-100 to-green-100 rounded-2xl p-6 mb-4 border-4 border-yellow-400">
            <div className="text-6xl font-bold text-gray-800 mb-2">
              {score} <span className="text-4xl text-gray-600">/ {totalQuestions}</span>
            </div>
            <p className="text-2xl font-bold text-gray-700">
              正答率: {percentage}%
            </p>
          </div>
          <p className="text-xl font-bold text-gray-700 mb-6">
            {message}
          </p>
        </div>

        {/* 結果詳細（オプション） */}
        {answers && answers.length > 0 && (
          <div className="mb-6 max-h-48 overflow-y-auto space-y-2 bg-gray-50 rounded-xl p-4 border-2 border-gray-200">
            <p className="text-sm font-bold text-gray-600 mb-2 text-center">📋 回答詳細</p>
            {answers.map((answer, index) => (
              <div 
                key={index} 
                className={`text-sm p-2 rounded-lg flex items-center gap-2 ${
                  answer.isCorrect 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}
              >
                <span className="text-lg">{answer.isCorrect ? '○' : '×'}</span>
                <span className="flex-1 truncate">問{index + 1}</span>
              </div>
            ))}
          </div>
        )}

        {/* リトライボタン */}
        <button
          onClick={onRetry}
          className="w-full bg-gradient-to-r from-red-600 to-green-600 text-white py-5 rounded-2xl font-bold text-xl hover:from-red-700 hover:to-green-700 transition-all transform hover:scale-105 flex items-center justify-center gap-3 shadow-xl border-4 border-yellow-400"
        >
          <RotateCcw className="w-7 h-7" />
          <span>もう一度挑戦する</span>
        </button>
        
        {/* フッター装飾 */}
        <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 text-5xl">
          🎁
        </div>
        <div className="absolute -bottom-3 left-8 text-3xl">🔔</div>
        <div className="absolute -bottom-3 right-8 text-3xl">🔔</div>
      </div>
    </div>
  );
};

export default ResultScreen;
