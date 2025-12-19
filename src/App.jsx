import React, { useState, useCallback, useEffect, useRef } from 'react';
import QuizDisplay from './components/QuizDisplay';
import ScoreBoard from './components/ScoreBoard';
import ResultScreen from './components/ResultScreen';
import VoiceRecognition from './components/VoiceRecognition';
import MotorProcessingOverlay from './components/MotorProcessingOverlay';
import { useObjectDetection } from './hooks/useObjectDetection';
import { useVoiceRecognition } from './hooks/useVoiceRecognition';
import { quizData } from './data/quizData';

const App = () => {
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [score, setScore] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [gameState, setGameState] = useState('playing');
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastAnswer, setLastAnswer] = useState(null);
  const [shouldPlayAudio, setShouldPlayAudio] = useState(false);
  const [respondentImage, setRespondentImage] = useState(null);
  const [isMotorProcessing, setIsMotorProcessing] = useState(false); // 🆕 モーター処理中フラグ
  const isProcessingRef = useRef(false);
  const audioPlayRequestRef = useRef(false);

  // 正解/不正解の音声を再生
  const playAnswerSound = useCallback((isCorrect) => {
    try {
      const audio = new Audio(isCorrect ? '/answer/correct.mp3' : '/answer/incorrect.mp3');
      audio.volume = 0.7;
      audio.play().catch(error => {
        console.error('音声再生エラー:', error);
      });
    } catch (error) {
      console.error('音声ファイル読み込みエラー:', error);
    }
  }, []);

  // モーター再開API呼び出し
  const resumeMotor = useCallback(async () => {
    try {
      const response = await fetch('http://localhost:8000/motor/resume', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        console.log('✓ モーター再開リクエスト送信');
      } else {
        console.error('❌ モーター再開エラー:', response.status);
      }
    } catch (error) {
      console.error('❌ モーター再開API呼び出しエラー:', error);
    }
  }, []);

  // 回答処理
  const handleAnswer = useCallback((userAnswer) => {
    if (isProcessingRef.current) {
      console.log('⏸️ 既に処理中のため、回答をスキップ');
      return;
    }
    
    console.log(`📝 回答受付: ${userAnswer ? 'まる' : 'ばつ'}`);
    isProcessingRef.current = true;
    
    // 現在の問題を取得
    const currentQuiz = quizData[currentQuestion];
    const isCorrect = userAnswer === currentQuiz.answer;
    
    console.log(`📍 現在の問題: ${currentQuestion + 1}/${quizData.length}`);
    
    // 回答直後に回答者画像をクリア
    setRespondentImage(null);
    console.log('🧹 回答者画像をクリア');
    
    // 正解/不正解の音声を再生
    playAnswerSound(isCorrect);
    
    // 状態を一括更新
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

    // 解説表示時間（2秒）
    setTimeout(() => {
      console.log('📖 解説表示終了');
      setShowFeedback(false);
      setLastAnswer(null);
      
      // 次の問題があるかチェック
      const nextQuestion = currentQuestion + 1;
      console.log(`🔍 次の問題判定: nextQuestion=${nextQuestion}, total=${quizData.length}`);
      
      if (nextQuestion < quizData.length) {
        console.log(`➡️ 次の問題へ移行: ${nextQuestion + 1}/${quizData.length}`);
        
        // モーター再開を非同期で実行（処理中画面が表示される）
        resumeMotor().then(() => {
          console.log('✅ モーター再開完了');
        });
        
        // 状態更新を確実に実行
        setTimeout(() => {
          setCurrentQuestion(nextQuestion);
          isProcessingRef.current = false;
          console.log(`✨ 問題${nextQuestion + 1}を表示、処理フラグリセット`);
        }, 100);
      } else {
        console.log(`🎉 クイズ終了（全${quizData.length}問完了）`);
        isProcessingRef.current = false;
        setGameState('finished');
      }
    }, 2000);
  }, [currentQuestion, playAnswerSound, resumeMotor]);

  // Vosk音声認識
  const {
    isListening: isVoiceListening,
    recognizedText: voiceRecognizedText,
    recognitionHistory,
    startListening: startVoiceListening,
    stopListening: stopVoiceListening,
    clearHistory: clearVoiceHistory,
    isSupported: isVoiceSupported,
    isConnected: isVoiceConnected,
    debugInfo: voiceDebugInfo
  } = useVoiceRecognition(handleAnswer);

  // 物体検出からの音声再生トリガー
  const handlePlayAudioTrigger = useCallback(() => {
    audioPlayRequestRef.current = true;
    setShouldPlayAudio(true);
    
    setTimeout(() => {
      audioPlayRequestRef.current = false;
      setShouldPlayAudio(false);
    }, 1000);
  }, []);

  // 人検出時のコールバック（回答者画像を受信）
  const handlePersonSelected = useCallback((snapshot) => {
    console.log('👤 回答者選択完了');
    setRespondentImage(snapshot);
    
    // 音声を自動再生
    console.log('🎵 問題音声を自動再生');
    handlePlayAudioTrigger();
  }, [handlePlayAudioTrigger]);

  // モーター処理状態のコールバック
  const handleMotorProcessing = useCallback((status) => {
    if (status === 'started') {
      console.log('🔄 モーター処理開始');
      setIsMotorProcessing(true);
    } else if (status === 'completed') {
      console.log('✓ モーター処理完了');
      setIsMotorProcessing(false);
    }
  }, []);

  const { isConnected: isDetectionConnected, personDetected, detectionCount } = useObjectDetection(handlePlayAudioTrigger, handlePersonSelected, handleMotorProcessing);

  // キーボードイベント
  useEffect(() => {
    const handleKeyPress = (event) => {
      if (showFeedback || gameState !== 'playing' || isMotorProcessing) {
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
  }, [handleAnswer, showFeedback, gameState, isMotorProcessing]);

  // フィードバック中は音声認識を一時停止
  useEffect(() => {
    if (showFeedback || isMotorProcessing) {
      if (isVoiceListening) {
        console.log('⏸️ フィードバック/モーター処理中：音声認識を一時停止');
        stopVoiceListening();
      }
    } else if (gameState === 'playing') {
      // フィードバック終了後、少し待ってから再開
      const restartTimer = setTimeout(() => {
        if (!isVoiceListening && isVoiceSupported && isVoiceConnected) {
          console.log('▶️ 音声認識を再開');
          startVoiceListening();
        }
      }, 300);
      
      return () => clearTimeout(restartTimer);
    }
  }, [showFeedback, gameState, isMotorProcessing]);

  const resetGame = useCallback(() => {
    console.log('🔄 ゲームをリセット中...');
    
    // すべての状態をクリア
    setShowFeedback(false);
    setLastAnswer(null);
    setRespondentImage(null);
    setIsMotorProcessing(false);
    isProcessingRef.current = false;
    audioPlayRequestRef.current = false;
    setShouldPlayAudio(false);
    
    // 少し待ってから初期化
    setTimeout(() => {
      setCurrentQuestion(0);
      setScore(0);
      setAnswers([]);
      setGameState('playing');
      clearVoiceHistory();
      
      console.log('✅ ゲームリセット完了');
      
      // モーター再開
      resumeMotor().then(() => {
        console.log('✅ モーター再開完了');
      });
    }, 100);
  }, [clearVoiceHistory, resumeMotor]);

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
      {/* 🆕 モーター処理中オーバーレイ */}
      <MotorProcessingOverlay isVisible={isMotorProcessing} />
      
      {/* 雪の結晶アニメーション（軽量化：減らして静的に） */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-10 left-10 text-white text-4xl opacity-70">❄️</div>
        <div className="absolute top-20 right-20 text-white text-3xl opacity-70">⛄</div>
        <div className="absolute bottom-20 left-20 text-white text-3xl opacity-70">🎄</div>
        <div className="absolute bottom-10 right-10 text-white text-4xl opacity-70">�</div>
      </div>
      
      <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-2xl w-full relative border-8 border-red-600" style={{
        backgroundImage: 'linear-gradient(to bottom, #ffffff 0%, #fff5f5 100%)',
        boxShadow: '0 0 40px rgba(255, 0, 0, 0.3), inset 0 0 20px rgba(0, 255, 0, 0.1)'
      }}>
        {/* クリスマス装飾 - ヘッダー */}
        <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 text-6xl">
          🎄
        </div>
        <div className="absolute -top-2 left-8 text-3xl opacity-80">⭐</div>
        <div className="absolute -top-2 right-8 text-3xl opacity-80">⭐</div>
        
        {/* ヘッダー */}
        <div className="mb-6 mt-4">
          <ScoreBoard score={score} currentQuestion={currentQuestion} />
        </div>

        {/* 接続ステータス */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${
            isDetectionConnected ? 'bg-green-50 border-2 border-green-600' : 'bg-gray-50 border-2 border-gray-300'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isDetectionConnected ? 'bg-green-600 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-xs font-medium ${isDetectionConnected ? 'text-green-800' : 'text-gray-600'}`}>
              🎄 物体検出: {isDetectionConnected ? '接続' : '切断'}
            </span>
          </div>

          <div className={`flex items-center gap-2 p-3 rounded-lg transition-colors ${
            isVoiceConnected ? 'bg-red-50 border-2 border-red-600' : 'bg-gray-50 border-2 border-gray-300'
          }`}>
            <div className={`w-3 h-3 rounded-full ${isVoiceConnected ? 'bg-red-600 animate-pulse' : 'bg-gray-400'}`}></div>
            <span className={`text-xs font-medium ${isVoiceConnected ? 'text-red-800' : 'text-gray-600'}`}>
              🎅 音声認識 (Vosk): {isVoiceConnected ? '接続' : '切断'}
            </span>
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
          respondentImage={respondentImage}
        />

        {/* Vosk音声認識 */}
        <VoiceRecognition
          isListening={isVoiceListening}
          recognizedText={voiceRecognizedText}
          recognitionHistory={recognitionHistory}
          disabled={showFeedback || isMotorProcessing}
          isSupported={isVoiceSupported}
          isConnected={isVoiceConnected}
          debugInfo={voiceDebugInfo}
          onStart={startVoiceListening}
          onStop={stopVoiceListening}
          onClearHistory={clearVoiceHistory}
        />

        {/* 手動回答ボタン */}
        <div className="flex gap-4 mb-4">
          <button
            onClick={() => handleAnswer(true)}
            disabled={showFeedback || isMotorProcessing}
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
            disabled={showFeedback || isMotorProcessing}
            className="flex-1 bg-gradient-to-br from-red-500 to-red-700 text-white py-4 rounded-xl font-bold text-xl hover:from-red-600 hover:to-red-800 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg hover:shadow-xl border-4 border-red-300"
            style={{ textShadow: '2px 2px 4px rgba(0,0,0,0.3)' }}
          >
            <div className="w-12 h-12 flex items-center justify-center text-3xl bg-white text-red-600 rounded-full border-4 border-white">
              ×
            </div>
            <span>🎅 ばつ</span>
          </button>
        </div>

        {/* 説明 */}
        <div className="text-center text-sm text-gray-700 bg-gradient-to-r from-red-50 to-green-50 p-4 rounded-lg border-2 border-red-300 relative overflow-hidden">
          <div className="absolute top-0 left-0 text-2xl">🎁</div>
          <div className="absolute top-0 right-0 text-2xl">🎁</div>
          <p className="mb-1 font-bold text-red-700">⭐ 回答方法 ⭐</p>
          <p className="mb-1">🤖 モーター回転中に人を検出 → 回答者選択</p>
          <p className="mb-1">🎤 音声: 「まる」「ばつ」と発話</p>
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
