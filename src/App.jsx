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
    console.log('物体検出により音声再生がトリガーされました');
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

  // フィードバック中は音声認識を一時停止、終了後に再開
  useEffect(() => {
    if (showFeedback) {
      console.log('フィードバック表示中: 音声認識を一時停止');
      if (isWhisperListening) {
        stopWhisperListening();
      }
    } else {
      // フィードバック終了後、少し遅延してから音声認識を再開
      const restartTimer = setTimeout(() => {
        if (!isWhisperListening && isWhisperSupported && isWhisperConnected) {
          console.log('フィードバック終了: 音声認識を再開');
          startWhisperListening();
        }
      }, 500);
      
      return () => clearTimeout(restartTimer);
    }
  }, [showFeedback, isWhisperListening, isWhisperSupported, isWhisperConnected, startWhisperListening, stopWhisperListening]);

  const resetGame = () => {
    setCurrentQuestion(0);
    setScore(0);
    setAnswers([]);
    setGameState('playing');
    setShowFeedback(false);
    setLastAnswer(null);
    isProcessingRef.current = false;
    clearWhisperHistory();
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
  
  // クイズデータが存在しない場合のガード
  if (!currentQuiz) {
    console.error('クイズデータが見つかりません:', currentQuestion);
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full text-center">
          <p className="text-xl text-gray-700">クイズデータの読み込み中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-2xl w-full">
        {/* ヘッダー */}
        <div className="mb-6">
          <ScoreBoard score={score} currentQuestion={currentQuestion} />
        </div>

        {/* 接続ステータス */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {/* 物体検出ステータス */}
          <div className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${
            isDetectionConnected ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isDetectionConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-xs font-medium ${isDetectionConnected ? 'text-green-700' : 'text-gray-600'}`}>
              物体検出: {isDetectionConnected ? '接続' : '切断'}
            </span>
          </div>

          {/* Whisper音声認識ステータス */}
          <div className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${
            isWhisperConnected ? 'bg-purple-50 border border-purple-200' : 'bg-gray-50 border border-gray-200'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isWhisperConnected ? 'bg-purple-500 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-xs font-medium ${isWhisperConnected ? 'text-purple-700' : 'text-gray-600'}`}>
              Whisper: {isWhisperConnected ? '接続' : '切断'}
            </span>
          </div>
        </div>

        {/* 人検出表示 */}
        {personDetected && (
          <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg animate-pulse">
            <span className="text-sm text-yellow-800 font-semibold">
              👤 人を検出中 ({detectionCount}人) - 3秒後に音声再生...
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

        {/* 手動回答ボタン */}
        <div className="flex gap-4 mb-4">
          <button
            onClick={() => handleAnswer(true)}
            disabled={showFeedback}
            className="flex-1 bg-green-500 text-white py-4 rounded-xl font-bold text-xl hover:bg-green-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg hover:shadow-xl"
          >
            <div className="w-12 h-12 rounded-full border-4 border-white flex items-center justify-center text-2xl">
              ○
            </div>
            まる
          </button>
          <button
            onClick={() => handleAnswer(false)}
            disabled={showFeedback}
            className="flex-1 bg-red-500 text-white py-4 rounded-xl font-bold text-xl hover:bg-red-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg hover:shadow-xl"
          >
            <div className="w-12 h-12 flex items-center justify-center text-3xl">
              ×
            </div>
            ばつ
          </button>
        </div>

        {/* 説明 */}
        <div className="text-center text-sm text-gray-500 bg-gray-50 p-3 rounded-lg border border-gray-200">
          <p className="mb-1 font-semibold">💡 回答方法</p>
          <p className="mb-1">🎤 音声: 「まる」「ばつ」と発話（Whisper + VAD認識）</p>
          <p>⌨️ キーボード: <kbd className="px-2 py-1 bg-gray-200 rounded text-xs">O</kbd> = まる、<kbd className="px-2 py-1 bg-gray-200 rounded text-xs">X</kbd> = ばつ</p>
        </div>
      </div>
    </div>
  );
};

export default App;
