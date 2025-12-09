import React, { useState, useCallback, useEffect, useRef } from 'react';
import QuizDisplay from './components/QuizDisplay';
import ScoreBoard from './components/ScoreBoard';
import ResultScreen from './components/ResultScreen';
import WhisperRecognition from './components/WhisperRecognition';
import { useObjectDetection } from './hooks/useObjectDetection';
import { useWhisperRecognition } from './hooks/useWhisperRecognition';
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

  // 回答処理
  const handleAnswer = useCallback((userAnswer) => {
    if (isProcessingRef.current) {
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
      
      // 次の問題があるかチェック
      const nextQuestion = currentQuestion + 1;
      if (nextQuestion < quizData.length) {
        setCurrentQuestion(nextQuestion);
      } else {
        // クイズ終了を確実に設定
        setGameState('finished');
      }
    }, 2000);
  }, [currentQuestion]);

  // Whisper音声認識
  const {
    isListening: isWhisperListening,
    recognizedText: whisperRecognizedText,
    recognitionHistory,
    startListening: startWhisperListening,
    stopListening: stopWhisperListening,
    clearHistory: clearWhisperHistory,
    isSupported: isWhisperSupported,
    isConnected: isWhisperConnected,
    debugInfo: whisperDebugInfo
  } = useWhisperRecognition(handleAnswer);

  // 物体検出からの音声再生トリガー
  const handlePlayAudioTrigger = useCallback(() => {
    audioPlayRequestRef.current = true;
    setShouldPlayAudio(true);
    
    setTimeout(() => {
      audioPlayRequestRef.current = false;
      setShouldPlayAudio(false);
    }, 1000);
  }, []);

  const { isConnected: isDetectionConnected, personDetected, detectionCount } = useObjectDetection(handlePlayAudioTrigger);

  // キーボードイベント
  useEffect(() => {
    const handleKeyPress = (event) => {
      if (showFeedback || gameState !== 'playing') {
        return;
      }

      const key = event.key.toLowerCase();
      
      if (key === 'o') {
        handleAnswer(true);
      }
      else if (key === 'x') {
        handleAnswer(false);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    
    return () => {
      window.removeEventListener('keydown', handleKeyPress);
    };
  }, [handleAnswer, showFeedback, gameState]);

  // フィードバック中は音声認識を一時停止、終了後に再開
  useEffect(() => {
    if (showFeedback) {
      if (isWhisperListening) {
        stopWhisperListening();
      }
    } else {
      // フィードバック終了後、少し遅延してから音声認識を再開
      const restartTimer = setTimeout(() => {
        if (!isWhisperListening && isWhisperSupported && isWhisperConnected) {
          startWhisperListening();
        }
      }, 500);
      
      return () => clearTimeout(restartTimer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showFeedback, isWhisperListening, isWhisperSupported, isWhisperConnected]);

  const resetGame = useCallback(() => {
    // すべての状態を確実にリセット
    setShowFeedback(false);
    setLastAnswer(null);
    isProcessingRef.current = false;
    audioPlayRequestRef.current = false;
    setShouldPlayAudio(false);
    
    // 少し遅延してから新しいゲームを開始（状態のクリーンアップを確実に）
    setTimeout(() => {
      setCurrentQuestion(0);
      setScore(0);
      setAnswers([]);
      setGameState('playing');
      clearWhisperHistory();
    }, 100);
  }, [clearWhisperHistory]);

  // クイズ終了画面
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
  
  // クイズデータが存在しない場合（エラー状態）
  if (!currentQuiz && gameState === 'playing') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-700 via-green-700 to-red-800 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center border-4 border-red-600">
          <p className="text-xl text-red-700 mb-4">⚠️ エラーが発生しました</p>
          <button
            onClick={resetGame}
            className="bg-gradient-to-r from-red-600 to-green-600 text-white py-3 px-6 rounded-xl font-bold hover:from-red-700 hover:to-green-700 transition"
          >
            最初から始める
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-700 via-green-700 to-red-800 flex items-center justify-center p-4 relative overflow-hidden">
      {/* 雪の結晶アニメーション */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-10 left-10 text-white text-4xl animate-bounce">❄️</div>
        <div className="absolute top-20 right-20 text-white text-3xl animate-pulse">⛄</div>
        <div className="absolute bottom-20 left-20 text-white text-3xl animate-bounce">🎄</div>
        <div className="absolute bottom-10 right-10 text-white text-4xl animate-pulse">🎅</div>
        <div className="absolute top-1/3 left-1/4 text-white text-2xl animate-pulse">✨</div>
        <div className="absolute top-2/3 right-1/3 text-white text-2xl animate-bounce">🎁</div>
      </div>
      
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-2xl w-full relative border-8 border-red-600" style={{
        backgroundImage: 'linear-gradient(to bottom, #ffffff 0%, #fff5f5 100%)',
        boxShadow: '0 0 40px rgba(255, 0, 0, 0.3), inset 0 0 20px rgba(0, 255, 0, 0.1)'
      }}>
        {/* クリスマス装飾 - ヘッダー */}
        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 text-6xl">
          🎄
        </div>
        <div className="absolute -top-2 left-8 text-3xl animate-pulse">⭐</div>
        <div className="absolute -top-2 right-8 text-3xl animate-pulse">⭐</div>
        
        {/* ヘッダー */}
        <div className="mb-6 mt-4">
          <ScoreBoard score={score} currentQuestion={currentQuestion} />
        </div>

        {/* 接続ステータス - クリスマステーマ */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {/* 物体検出ステータス */}
          <div className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${
            isDetectionConnected ? 'bg-green-50 border-2 border-green-600' : 'bg-gray-50 border-2 border-gray-300'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isDetectionConnected ? 'bg-green-600 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-xs font-medium ${isDetectionConnected ? 'text-green-800' : 'text-gray-600'}`}>
              🎄 物体検出: {isDetectionConnected ? '接続' : '切断'}
            </span>
          </div>

          {/* Whisper音声認識ステータス */}
          <div className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${
            isWhisperConnected ? 'bg-red-50 border-2 border-red-600' : 'bg-gray-50 border-2 border-gray-300'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isWhisperConnected ? 'bg-red-600 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-xs font-medium ${isWhisperConnected ? 'text-red-800' : 'text-gray-600'}`}>
              🎅 Whisper: {isWhisperConnected ? '接続' : '切断'}
            </span>
          </div>
        </div>

        {/* 人検出表示 - クリスマステーマ */}
        {personDetected && (
          <div className="mb-4 p-3 bg-yellow-50 border-2 border-yellow-400 rounded-lg animate-pulse">
            <span className="text-sm text-yellow-800 font-semibold">
              🎁 人を検出中 ({detectionCount}人) - 3秒後に音声再生...
            </span>
          </div>
        )}

        {/* クイズ表示 */}
        <QuizDisplay
          quiz={currentQuiz}
          currentQuestion={currentQuestion}
          totalQuestions={quizData.length}
          showFeedback={showFeedback}
          lastAnswer={lastAnswer}
          shouldPlayAudio={shouldPlayAudio}
        />

        {/* Whisper音声認識 */}
        <WhisperRecognition
          isListening={isWhisperListening}
          recognizedText={whisperRecognizedText}
          recognitionHistory={recognitionHistory}
          disabled={showFeedback}
          isSupported={isWhisperSupported}
          isConnected={isWhisperConnected}
          debugInfo={whisperDebugInfo}
          onStart={startWhisperListening}
          onStop={stopWhisperListening}
          onClearHistory={clearWhisperHistory}
        />

        {/* 手動回答ボタン - クリスマステーマ */}
        <div className="flex gap-4 mb-4">
          <button
            onClick={() => handleAnswer(true)}
            disabled={showFeedback}
            className="flex-1 bg-gradient-to-br from-green-500 to-green-700 text-white py-4 rounded-xl font-bold text-xl hover:from-green-600 hover:to-green-800 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg hover:shadow-xl border-4 border-green-300"
            style={{ textShadow: '2px 2px 4px rgba(0,0,0,0.3)' }}
          >
            <div className="w-12 h-12 rounded-full border-4 border-white flex items-center justify-center text-2xl bg-white text-green-600">
              ○
            </div>
            <span>🎄 まる</span>
          </button>
          <button
            onClick={() => handleAnswer(false)}
            disabled={showFeedback}
            className="flex-1 bg-gradient-to-br from-red-500 to-red-700 text-white py-4 rounded-xl font-bold text-xl hover:from-red-600 hover:to-red-800 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg hover:shadow-xl border-4 border-red-300"
            style={{ textShadow: '2px 2px 4px rgba(0,0,0,0.3)' }}
          >
            <div className="w-12 h-12 flex items-center justify-center text-3xl bg-white text-red-600 rounded-full border-4 border-white">
              ×
            </div>
            <span>🎅 ばつ</span>
          </button>
        </div>

        {/* 説明 - クリスマステーマ */}
        <div className="text-center text-sm text-gray-700 bg-gradient-to-r from-red-50 to-green-50 p-4 rounded-lg border-2 border-red-300 relative overflow-hidden">
          <div className="absolute top-0 left-0 text-2xl">🎁</div>
          <div className="absolute top-0 right-0 text-2xl">🎁</div>
          <p className="mb-1 font-bold text-red-700">⭐ 回答方法 ⭐</p>
          <p className="mb-1">🎤 音声: 「まる」「ばつ」と発話（Whisper + VAD認識）</p>
          <p>⌨️ キーボード: <kbd className="px-2 py-1 bg-red-200 rounded text-xs font-semibold">O</kbd> = まる、<kbd className="px-2 py-1 bg-green-200 rounded text-xs font-semibold">X</kbd> = ばつ</p>
        </div>
        
        {/* クリスマス装飾 - フッター */}
        <div className="absolute -bottom-3 left-1/2 transform -translate-x-1/2 text-4xl">
          🎁
        </div>
        <div className="absolute -bottom-2 left-4 text-2xl">🔔</div>
        <div className="absolute -bottom-2 right-4 text-2xl">🔔</div>
      </div>
    </div>
  );
};

export default App;
