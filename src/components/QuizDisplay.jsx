import React, { useEffect, useRef } from 'react';
import { Check, X } from 'lucide-react';
import AudioPlayer from './AudioPlayer';

const QuizDisplay = ({ quiz, currentQuestion, totalQuestions, showFeedback, lastAnswer, shouldPlayAudio = false, respondentImage = null }) => {
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
      console.log('🔊 物体検出トリガーにより音声を再生します');
      audioPlayerRef.current.play();
    }
  }, [shouldPlayAudio]);

  // 回答者画像の状態をログ
  useEffect(() => {
    if (respondentImage) {
      console.log('📷 回答者画像を表示');
    } else {
      console.log('🧹 回答者画像なし');
    }
  }, [respondentImage]);

  return (
    <>
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
          
          {/* 回答者画像がある場合は横に表示 */}
          {respondentImage && (
            <div className="mb-4 flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="relative">
                  <img 
                    src={`data:image/jpeg;base64,${respondentImage}`} 
                    alt="回答者" 
                    className="w-32 h-32 rounded-xl border-4 border-yellow-400 shadow-lg object-cover"
                  />
                  <div className="absolute -top-2 -right-2 bg-yellow-400 text-red-700 font-bold px-2 py-1 rounded-full text-xs border-2 border-red-600 animate-pulse">
                    👤 回答者
                  </div>
                </div>
              </div>
              <div className="flex-1 flex items-center justify-center bg-yellow-50 rounded-lg p-3 border-2 border-yellow-400">
                <p className="text-lg font-bold text-red-700 text-center">
                  🎉 あなたが回答者です！🎉
                </p>
              </div>
            </div>
          )}
          
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
      </div>

      {/* フィードバック表示 - 画面全体オーバーレイ */}
      {showFeedback && lastAnswer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in" style={{
          background: lastAnswer.isCorrect 
            ? 'rgba(34, 197, 94, 0.95)' 
            : 'rgba(239, 68, 68, 0.95)'
        }}>
          {/* 背景アニメーション */}
          <div className="absolute inset-0 overflow-hidden">
            {lastAnswer.isCorrect ? (
              <>
                <div className="absolute top-10 left-10 text-9xl animate-bounce">🎉</div>
                <div className="absolute top-10 right-10 text-9xl animate-bounce" style={{animationDelay: '0.1s'}}>🎊</div>
                <div className="absolute bottom-10 left-10 text-8xl animate-pulse">✨</div>
                <div className="absolute bottom-10 right-10 text-8xl animate-pulse" style={{animationDelay: '0.2s'}}>⭐</div>
                <div className="absolute top-1/3 left-1/4 text-7xl animate-bounce" style={{animationDelay: '0.15s'}}>🎄</div>
                <div className="absolute top-2/3 right-1/4 text-7xl animate-bounce" style={{animationDelay: '0.25s'}}>🎁</div>
              </>
            ) : (
              <>
                <div className="absolute top-10 left-10 text-9xl animate-pulse">😢</div>
                <div className="absolute top-10 right-10 text-9xl animate-pulse" style={{animationDelay: '0.15s'}}>💧</div>
                <div className="absolute bottom-10 left-10 text-8xl animate-bounce">⛄</div>
                <div className="absolute bottom-10 right-10 text-8xl animate-bounce" style={{animationDelay: '0.2s'}}>😭</div>
                <div className="absolute top-1/3 left-1/4 text-7xl animate-pulse" style={{animationDelay: '0.1s'}}>💔</div>
                <div className="absolute top-2/3 right-1/4 text-7xl animate-pulse" style={{animationDelay: '0.25s'}}>😔</div>
              </>
            )}
          </div>
          
          {/* メインコンテンツ */}
          <div className="relative z-10 max-w-4xl w-full">
            {/* 巨大な正解/不正解表示 */}
            {lastAnswer.isCorrect ? (
              <div className="text-center mb-8 animate-bounce">
                <div className="flex items-center justify-center gap-6 mb-8">
                  <div className="text-9xl">🎉</div>
                  <div className="text-9xl">🎄</div>
                  <div className="text-9xl">🎊</div>
                </div>
                <div className="bg-white rounded-3xl p-16 shadow-2xl transform hover:scale-105 transition-transform">
                  <div className="flex items-center justify-center gap-8">
                    <Check className="w-32 h-32 text-green-600" strokeWidth={6} />
                    <div className="text-9xl font-black text-green-700" style={{
                      textShadow: '5px 5px 10px rgba(0,0,0,0.3)',
                      WebkitTextStroke: '4px #15803d',
                      fontSize: '12rem'
                    }}>
                      正解
                    </div>
                    <Check className="w-32 h-32 text-green-600" strokeWidth={6} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center mb-8 animate-pulse">
                <div className="flex items-center justify-center gap-6 mb-8">
                  <div className="text-9xl">😢</div>
                  <div className="text-9xl">⛄</div>
                  <div className="text-9xl">💧</div>
                </div>
                <div className="bg-white rounded-3xl p-16 shadow-2xl transform hover:scale-105 transition-transform">
                  <div className="flex items-center justify-center gap-8">
                    <X className="w-32 h-32 text-red-600" strokeWidth={6} />
                    <div className="text-9xl font-black text-red-700 whitespace-nowrap" style={{
                      textShadow: '5px 5px 10px rgba(0,0,0,0.3)',
                      WebkitTextStroke: '4px #991b1b',
                      fontSize: '10rem'
                    }}>
                      不正解
                    </div>
                    <X className="w-32 h-32 text-red-600" strokeWidth={6} />
                  </div>
                </div>
              </div>
            )}
            
            {/* 解説 */}
            <div className="bg-white rounded-3xl p-8 shadow-2xl border-8 border-yellow-400">
              <div className="flex items-center justify-center gap-3 mb-4">
                <div className="text-4xl">📝</div>
                <p className="text-4xl font-black text-gray-800">解説</p>
                <div className="text-4xl">📝</div>
              </div>
              <p className="text-3xl text-gray-900 font-bold leading-relaxed">{quiz.explanation}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default QuizDisplay;
