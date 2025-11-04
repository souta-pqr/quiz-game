import { useState, useEffect, useCallback, useRef } from 'react';

export const useVoiceRecognition = (onAnswer) => {
  const [isListening, setIsListening] = useState(false);
  const [recognizedText, setRecognizedText] = useState('');
  const [isSupported, setIsSupported] = useState(false);
  const recognitionRef = useRef(null);
  const isActiveRef = useRef(true);
  const isStartingRef = useRef(false);
  const restartTimeoutRef = useRef(null);
  const consecutiveErrorsRef = useRef(0);

  useEffect(() => {
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
        // エラーカウントはここではリセットしない！
      };

      recognitionInstance.onresult = (event) => {
        // 認識成功時のみリセット
        consecutiveErrorsRef.current = 0;
        
        const lastResultIndex = event.results.length - 1;
        const transcript = event.results[lastResultIndex][0].transcript;
        
        if (event.results[lastResultIndex].isFinal) {
          console.log('認識結果:', transcript);
          setRecognizedText(transcript);
          
          if (transcript.includes('まる') || transcript.includes('マル') || transcript.includes('丸')) {
            onAnswer(true);
            setRecognizedText('');
          }
          else if (transcript.includes('ばつ') || transcript.includes('バツ') || transcript.includes('ペケ')) {
            onAnswer(false);
            setRecognizedText('');
          }
        } else {
          setRecognizedText(transcript);
        }
      };

      recognitionInstance.onerror = (event) => {
        console.error('音声認識エラー:', event.error);
        setIsListening(false);
        isStartingRef.current = false;
        
        if (event.error === 'network') {
          consecutiveErrorsRef.current++;
          console.log(`連続エラー数: ${consecutiveErrorsRef.current}`);
          
          if (consecutiveErrorsRef.current >= 3) {
            console.error('⚠️ 音声認識が利用できません（ネットワークエラー）');
            console.error('手動ボタンで回答してください');
            isActiveRef.current = false;
            setIsSupported(false);
            setRecognizedText('');
            return;
          }
        }
        
        if (event.error === 'aborted') {
          return;
        }
      };

      recognitionInstance.onend = () => {
        console.log('音声認識終了');
        setIsListening(false);
        isStartingRef.current = false;
        
        if (consecutiveErrorsRef.current >= 3) {
          console.log('エラー上限到達 - 再起動しません');
          isActiveRef.current = false;
          return;
        }
        
        if (isActiveRef.current) {
          if (restartTimeoutRef.current) {
            clearTimeout(restartTimeoutRef.current);
          }
          
          const delay = consecutiveErrorsRef.current > 0 ? 3000 : 500;
          
          restartTimeoutRef.current = setTimeout(() => {
            if (isActiveRef.current && recognitionRef.current && !isStartingRef.current) {
              console.log('音声認識を再起動します...');
              isStartingRef.current = true;
              try {
                recognitionRef.current.start();
              } catch (e) {
                console.log('再開試行エラー:', e);
                isStartingRef.current = false;
              }
            }
          }, delay);
        }
      };

      recognitionRef.current = recognitionInstance;
      
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
      }, 1000);
      
      return () => {
        clearTimeout(initTimer);
      };
    } else {
      console.log('このブラウザは音声認識に対応していません');
      setIsSupported(false);
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
    if (recognitionRef.current && !isStartingRef.current && isSupported) {
      isActiveRef.current = true;
      consecutiveErrorsRef.current = 0;
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
  }, [isSupported]);

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
