// src/App.jsx - 音声認識部分を削除
import React, { useState, useCallback, useEffect, useRef } from 'react';
import QuizDisplay from './components/QuizDisplay';
import ScoreBoard from './components/ScoreBoard';
import ResultScreen from './components/ResultScreen';
import { useObjectDetection } from './hooks/useObjectDetection';
import { quizData } from './data/quizData';

const App = () => {
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [score, setScore] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [gameState, setGameState] = useState('playing');
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastAnswer, setLastAnswer] = useState(null);
  const [shouldPlayAudio, setShouldPlayAudio] = useState(false);
  const isProcessingRef = useRef(false);
  const audioPlayRequestRef = useRef(false);

  // 物体検出からの音声再生トリガー
  const handlePlayAudioTrigger = useCallback(() => {
    console.log('物体検出により音声再生がトリガーされました');
    audioPlayRequestRef.current = true;
    setShouldPlayAudio(true);
    
    setTimeout(() => {
      audioPlayRequestRef.current = false;
      setShouldPlayAudio(false);
    }, 1000);
  }, []);

  const { isConnected, personDetected, detectionCount } = useObjectDetection(handlePlayAudioTrigger);

  const handleAnswer = useCallback((userAnswer) => {
    if (isProcessingRef.current) {
      console.log('回答処理中のため無視');
      return;
    }
    
    isProcessingRef.current = true;
    
    const currentQuiz = quizData[currentQuestion];
    const isCorrect = userAnswer === currentQuiz.answer;
    
    setLastAnswer({ isCorrect, userAnswer });
    setShowFeedback(true);

    const newAnswer = {
      questionId: currentQuiz.id,
      userAnswer,
      isCorrect,
      question: currentQuiz.question
    };
    
    setAnswers(prev => [...prev, newAnswer]);
    
    if (isCorrect) {
      setScore(prev => prev + 1);
    }

    setTimeout(() => {
      setShowFeedback(false);
      isProcessingRef.current = false;
      
      if (currentQuestion < quizData.length - 1) {
        setCurrentQuestion(prev => prev + 1);
      } else {
        setGameState('finished');
      }
    }, 2000);
  }, [currentQuestion]);

  // キーボードイベント
  useEffect(() => {
    const handleKeyPress = (event) => {
      if (showFeedback || gameState !== 'playing') {
        return;
      }

      const key = event.key.toLowerCase();
      
      if (key === 'o') {
        console.log('キーボード入力: まる');
        handleAnswer(true);
      }
      else if (key === 'x') {
        console.log('キーボード入力: ばつ');
        handleAnswer(false);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    
    return () => {
      window.removeEventListener('keydown', handleKeyPress);
    };
  }, [handleAnswer, showFeedback, gameState]);

  const resetGame = () => {
    setCurrentQuestion(0);
    setScore(0);
    setAnswers([]);
    setGameState('playing');
    setShowFeedback(false);
    setLastAnswer(null);
    isProcessingRef.current = false;
  };

  if (gameState === 'finished') {
    return (
      <ResultScreen
        score={score}
        totalQuestions={quizData.length}
        answers={answers}
        onRetry={resetGame}
      />
    );
  }

  const currentQuiz = quizData[currentQuestion];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-2xl w-full">
        {/* ヘッダー */}
        <div className="mb-6">
          <ScoreBoard score={score} currentQuestion={currentQuestion} />
        </div>

        {/* 物体検出ステータス */}
        <div className="mb-4">
          <div className={`flex items-center gap-2 p-3 rounded-lg ${
            isConnected ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-sm font-medium ${isConnected ? 'text-green-700' : 'text-gray-600'}`}>
              {isConnected ? '物体検出: 接続中' : '物体検出: 切断中'}
            </span>
            {personDetected && (
              <span className="ml-auto text-sm text-blue-700 font-semibold">
                👤 人を検出中 ({detectionCount}人) - 3秒後に再生...
              </span>
            )}
          </div>
        </div>

        {/* クイズ表示 */}
        <QuizDisplay
          quiz={currentQuiz}
          currentQuestion={currentQuestion}
          totalQuestions={quizData.length}
          showFeedback={showFeedback}
          lastAnswer={lastAnswer}
          shouldPlayAudio={shouldPlayAudio}
        />

        {/* 手動回答ボタン */}
        <div className="flex gap-4 mb-4">
          <button
            onClick={() => handleAnswer(true)}
            disabled={showFeedback}
            className="flex-1 bg-green-500 text-white py-4 rounded-xl font-bold text-xl hover:bg-green-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <div className="w-12 h-12 rounded-full border-4 border-white flex items-center justify-center text-2xl">
              ○
            </div>
            まる
          </button>
          <button
            onClick={() => handleAnswer(false)}
            disabled={showFeedback}
            className="flex-1 bg-red-500 text-white py-4 rounded-xl font-bold text-xl hover:bg-red-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <div className="w-12 h-12 flex items-center justify-center text-3xl">
              ×
            </div>
            ばつ
          </button>
        </div>

        {/* 説明 */}
        <div className="text-center text-sm text-gray-500">
          ボタンをクリック、またはキーボード（<kbd className="px-2 py-1 bg-gray-200 rounded">O</kbd> = まる、<kbd className="px-2 py-1 bg-gray-200 rounded">X</kbd> = ばつ）で回答してください
        </div>
      </div>
    </div>
  );
};

export default App;
