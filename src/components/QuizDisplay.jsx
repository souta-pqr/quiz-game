import React from 'react';
import { Check, X } from 'lucide-react';

const QuizDisplay = ({ quiz, currentQuestion, totalQuestions, showFeedback, lastAnswer }) => {
  const progress = ((currentQuestion + 1) / totalQuestions) * 100;

  return (
    <div className="mb-8">
      {/* 進行状況バー */}
      <div className="mb-4">
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-blue-600 h-3 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-600 mt-2">
          問題 {currentQuestion + 1} / {totalQuestions}
        </p>
      </div>

      {/* クイズ問題 */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-6 rounded-xl mb-6">
        <p className="text-xl font-semibold text-gray-800 text-center leading-relaxed">
          {quiz.question}
        </p>
      </div>

      {/* フィードバック表示 */}
      {showFeedback && lastAnswer && (
        <div className={`p-4 rounded-lg mb-4 animate-fade-in ${
          lastAnswer.isCorrect ? 'bg-green-100' : 'bg-red-100'
        }`}>
          <div className="flex items-center gap-2 mb-2">
            {lastAnswer.isCorrect ? (
              <>
                <Check className="w-6 h-6 text-green-600" />
                <span className="text-green-800 font-bold">正解!</span>
              </>
            ) : (
              <>
                <X className="w-6 h-6 text-red-600" />
                <span className="text-red-800 font-bold">不正解</span>
              </>
            )}
          </div>
          <p className="text-sm text-gray-700">{quiz.explanation}</p>
        </div>
      )}
    </div>
  );
};

export default QuizDisplay;
