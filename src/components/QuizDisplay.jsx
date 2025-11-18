import React, { useEffect, useRef } from 'react';
import { Check, X } from 'lucide-react';
import AudioPlayer from './AudioPlayer';

const QuizDisplay = ({ quiz, currentQuestion, totalQuestions, showFeedback, lastAnswer, shouldPlayAudio = false }) => {
  // quizがundefinedの場合のガード
  if (!quiz) {
    return (
      <div className="mb-8 p-6 bg-yellow-50 rounded-xl">
        <p className="text-center text-gray-600">クイズデータを読み込み中...</p>
      </div>
    );
  }
  
  const progress = ((currentQuestion + 1) / totalQuestions) * 100;
  const audioSrc = `/audio/question_${quiz.id}.wav`;
  const audioPlayerRef = useRef(null);

  // 物体検出からのトリガーで音声再生
  useEffect(() => {
    if (shouldPlayAudio && audioPlayerRef.current) {
      console.log('物体検出トリガーにより音声を再生します');
      audioPlayerRef.current.play();
    }
  }, [shouldPlayAudio]);

  return (
    <div className="mb-8">
      {/* 進行状況バー - クリスマステーマ */}
      <div className="mb-4 relative">
        <div className="absolute -left-2 top-0 text-xl">🎄</div>
        <div className="absolute -right-2 top-0 text-xl">🎄</div>
        <div className="w-full bg-red-100 rounded-full h-4 border-2 border-red-300">
          <div
            className="bg-gradient-to-r from-green-500 to-red-500 h-full rounded-full transition-all duration-500 relative overflow-hidden"
            style={{ width: `${progress}%` }}
          >
            <div className="absolute inset-0 bg-white opacity-30 animate-pulse"></div>
          </div>
        </div>
        <p className="text-sm text-red-700 mt-2 font-semibold text-center">
          🎅 問題 {currentQuestion + 1} / {totalQuestions} 🎁
        </p>
      </div>

      {/* クイズ問題 - クリスマステーマ */}
      <div className="bg-gradient-to-br from-red-50 via-white to-green-50 p-6 rounded-xl mb-4 border-4 border-double border-red-400 relative shadow-lg">
        <div className="absolute -top-3 -left-3 text-3xl animate-pulse">⭐</div>
        <div className="absolute -top-3 -right-3 text-3xl animate-pulse">⭐</div>
        <div className="absolute -bottom-3 -left-3 text-2xl">🎁</div>
        <div className="absolute -bottom-3 -right-3 text-2xl">🎁</div>
        
        <p className="text-xl font-bold text-gray-800 text-center leading-relaxed mb-4 relative z-10">
          {quiz.question}
        </p>
        
        {/* 音声プレイヤー */}
        <div className="flex justify-center relative z-10">
          <AudioPlayer 
            ref={audioPlayerRef}
            audioSrc={audioSrc} 
            autoPlay={false} 
          />
        </div>
      </div>

      {/* フィードバック表示 - クリスマステーマ */}
      {showFeedback && lastAnswer && (
        <div className={`p-5 rounded-xl mb-4 animate-fade-in border-4 shadow-lg ${
          lastAnswer.isCorrect 
            ? 'bg-gradient-to-br from-green-100 to-green-200 border-green-500' 
            : 'bg-gradient-to-br from-red-100 to-red-200 border-red-500'
        }`}>
          <div className="flex items-center gap-2 mb-2">
            {lastAnswer.isCorrect ? (
              <>
                <div className="text-5xl">🎉</div>
                <Check className="w-8 h-8 text-green-700" />
                <span className="text-green-900 font-bold text-2xl">正解!</span>
                <div className="text-3xl ml-2">🎄</div>
              </>
            ) : (
              <>
                <div className="text-4xl">😢</div>
                <X className="w-8 h-8 text-red-700" />
                <span className="text-red-900 font-bold text-2xl">不正解</span>
                <div className="text-3xl ml-2">⛄</div>
              </>
            )}
          </div>
          <p className="text-base text-gray-800 font-medium mt-2">{quiz.explanation}</p>
        </div>
      )}
    </div>
  );
};

export default QuizDisplay;
