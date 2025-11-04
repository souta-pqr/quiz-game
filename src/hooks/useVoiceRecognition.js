// src/hooks/useVoiceRecognition.js を以下のように修正
import { useState, useEffect, useCallback, useRef } from 'react';

export const useVoiceRecognition = (onAnswer) => {
  const [isListening, setIsListening] = useState(false);
  const [recognizedText, setRecognizedText] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef(null);
  const isActiveRef = useRef(true);
  const isStartingRef = useRef(false);
  const restartTimeoutRef = useRef(null);
  const errorCountRef = useRef(0); // エラーカウンターを追加
  const lastErrorTimeRef = useRef(0); // 最後のエラー時刻

  useEffect(() => {
    // 音声認識のサポート確認
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      setIsSupported(true);
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognitionInstance = new SpeechRecognition();
      
      recognitionInstance.lang = 'ja-JP';
      recognitionInstance.continuous = true;
      recognitionInstance.interimResults = true;

      recognitionInstance.onstart = () => {
        console.log('音声認識開始');
        setIsListening(true);
        isStartingRef.current = false;
        errorCountRef.current = 0; // 開始成功時にエラーカウントをリセット
      };

      recognitionInstance.onresult = (event) => {
        const lastResultIndex = event.results.length - 1;
        const transcript = event.results[lastResultIndex][0].transcript;
        
        // 最終結果のみ処理
        if (event.results[lastResultIndex].isFinal) {
          console.log('認識結果:', transcript);
          setRecognizedText(transcript);
          
          // 「まる」「マル」「○」を認識
          if (transcript.includes('まる') || transcript.includes('マル') || transcript.includes('丸')) {
            onAnswer(true);
            setRecognizedText('');
          }
          // 「ばつ」「バツ」「×」を認識
          else if (transcript.includes('ばつ') || transcript.includes('バツ') || transcript.includes('ペケ')) {
            onAnswer(false);
            setRecognizedText('');
          }
        } else {
          // 中間結果を表示
          setRecognizedText(transcript);
        }
      };

      recognitionInstance.onerror = (event) => {
        console.error('音声認識エラー:', event.error);
        setIsListening(false);
        isStartingRef.current = false;
        
        // networkエラーの場合は再試行を制限
        if (event.error === 'network') {
          const now = Date.now();
          
          // 1秒以内の連続エラーをカウント
          if (now - lastErrorTimeRef.current < 1000) {
            errorCountRef.current++;
          } else {
            errorCountRef.current = 1;
          }
          lastErrorTimeRef.current = now;
          
          // 3回連続でネットワークエラーが発生したら再試行を停止
          if (errorCountRef.current >= 3) {
            console.error('音声認識が利用できません。ネットワークエラーが連続して発生しました。');
            isActiveRef.current = false;
            setIsSupported(false); // サポート対象外として扱う
            return;
          }
        }
        
        // abortedエラーは無視（手動停止によるもの）
        if (event.error === 'aborted') {
          return;
        }
        
        // no-speechエラーの場合は自動再開
        if (event.error === 'no-speech' && isActiveRef.current) {
          if (restartTimeoutRef.current) {
            clearTimeout(restartTimeoutRef.current);
          }
          restartTimeoutRef.current = setTimeout(() => {
            if (isActiveRef.current && recognitionRef.current && !isStartingRef.current) {
              isStartingRef.current = true;
              try {
                recognitionRef.current.start();
              } catch (e) {
                console.log('再開エラー:', e);
                isStartingRef.current = false;
              }
            }
          }, 300);
        }
      };

      recognitionInstance.onend = () => {
        console.log('音声認識終了');
        setIsListening(false);
        isStartingRef.current = false;
        
        // 自動的に再開（ただしエラーカウントが上限に達していない場合のみ）
        if (isActiveRef.current && errorCountRef.current < 3) {
          if (restartTimeoutRef.current) {
            clearTimeout(restartTimeoutRef.current);
          }
          restartTimeoutRef.current = setTimeout(() => {
            if (isActiveRef.current && recognitionRef.current && !isStartingRef.current) {
              isStartingRef.current = true;
              try {
                recognitionRef.current.start();
              } catch (e) {
                console.log('再開試行:', e);
                isStartingRef.current = false;
              }
            }
          }, 1000); // 待機時間を1秒に延長
        }
      };

      recognitionRef.current = recognitionInstance;
      
      // 初回起動
      const initTimer = setTimeout(() => {
        if (recognitionRef.current && isActiveRef.current && !isStartingRef.current) {
          isStartingRef.current = true;
          try {
            recognitionRef.current.start();
          } catch (e) {
            if (e.message && e.message.includes('already started')) {
              console.log('音声認識は既に開始されています');
            } else {
              console.log('初回起動エラー:', e);
            }
            isStartingRef.current = false;
          }
        }
      }, 500);
      
      return () => {
        clearTimeout(initTimer);
      };
    }

    return () => {
      isActiveRef.current = false;
      if (restartTimeoutRef.current) {
        clearTimeout(restartTimeoutRef.current);
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          console.log('停止エラー:', e);
        }
      }
    };
  }, [onAnswer]);

  const startListening = useCallback(() => {
    if (recognitionRef.current && !isStartingRef.current) {
      isActiveRef.current = true;
      errorCountRef.current = 0; // 手動開始時にエラーカウントをリセット
      setRecognizedText('');
      
      if (restartTimeoutRef.current) {
        clearTimeout(restartTimeoutRef.current);
      }
      
      isStartingRef.current = true;
      try {
        recognitionRef.current.start();
      } catch (e) {
        if (e.message && e.message.includes('already started')) {
          console.log('音声認識は既に開始されています');
          setIsListening(true);
        } else {
          console.log('開始エラー:', e);
        }
        isStartingRef.current = false;
      }
    }
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      isActiveRef.current = false;
      isStartingRef.current = false;
      
      if (restartTimeoutRef.current) {
        clearTimeout(restartTimeoutRef.current);
      }
      
      try {
        recognitionRef.current.stop();
      } catch (e) {
        if (e.message && !e.message.includes('already')) {
          console.log('停止エラー:', e);
        }
      }
    }
  }, []);

  return {
    isListening,
    recognizedText,
    startListening,
    stopListening,
    isSupported
  };
};
