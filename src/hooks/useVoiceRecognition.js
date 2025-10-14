import { useState, useEffect, useCallback, useRef } from 'react';

export const useVoiceRecognition = (onAnswer) => {
  const [isListening, setIsListening] = useState(false);
  const [recognizedText, setRecognizedText] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef(null);
  const isActiveRef = useRef(true);
  const isStartingRef = useRef(false);
  const restartTimeoutRef = useRef(null);

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
        
        // 自動的に再開
        if (isActiveRef.current) {
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
          }, 300);
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
            // already startedエラーは無視
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
      setRecognizedText('');
      
      if (restartTimeoutRef.current) {
        clearTimeout(restartTimeoutRef.current);
      }
      
      isStartingRef.current = true;
      try {
        recognitionRef.current.start();
      } catch (e) {
        // already startedエラーは無視
        if (e.message && e.message.includes('already started')) {
          console.log('音声認識は既に開始されています');
          // 既に開始されている場合は状態を更新
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
        // 既に停止している場合は無視
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
