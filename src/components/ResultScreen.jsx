import React from 'react';
import { Trophy, RotateCcw, Check, X } from 'lucide-react';

const ResultScreen = ({ score, totalQuestions, answers, onRetry }) => {
  const percentage = Math.round((score / totalQuestions) * 100);

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full">
        <div className="text-center mb-6">
          <Trophy className="w-20 h-20 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-3xl font-bold text-gray-800 mb-2">クイズ終了!</h2>
          <div className="text-6xl font-bold text-purple-600 my-4">
            {score} / {totalQuestions}
          </div>
          <p className="text-xl text-gray-600">
            正答率: {percentage}%
          </p>
        </div>

        <div className="space-y-3 mb-6">
          {answers.map((answer, index) => (
            <div 
              key={index} 
              className={`p-3 rounded-lg ${
                answer.isCorrect ? 'bg-green-100' : 'bg-red-100'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-700 flex-1">
                  問{index + 1}: {answer.question}
                </span>
                {answer.isCorrect ? (
                  <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
                ) : (
                  <X className="w-5 h-5 text-red-600 flex-shrink-0" />
                )}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={onRetry}
          className="w-full bg-purple-600 text-white py-3 rounded-lg font-semibold hover:bg-purple-700 transition flex items-center justify-center gap-2"
        >
          <RotateCcw className="w-5 h-5" />
          もう一度挑戦
        </button>
      </div>
    </div>
  );
};

export default ResultScreen;
