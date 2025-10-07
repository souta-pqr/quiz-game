import { useState, useEffect, useCallback } from 'react';

export const useVoiceRecognition = (onAnswer) => {
  const [isListening, setIsListening] = useState(false);
  const [recognizedText, setRecognizedText] = useState('');
  const [recognition, setRecognition] = useState(null);
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    // 音声認識のサポート確認
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      setIsSupported(true);
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognitionInstance = new SpeechRecognition();
      
      recognitionInstance.lang = 'ja-JP';
      recognitionInstance.continuous = false;
      recognitionInstance.interimResults = false;

      recognitionInstance.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setRecognizedText(transcript);
        
        // 「まる」「マル」「○」を認識
        if (transcript.includes('まる') || transcript.includes('マル') || transcript.includes('丸')) {
          onAnswer(true);
        }
        // 「ばつ」「バツ」「×」を認識
        else if (transcript.includes('ばつ') || transcript.includes('バツ') || transcript.includes('ペケ')) {
          onAnswer(false);
        } else {
          setRecognizedText('「まる」または「ばつ」と言ってください');
        }
        
        setIsListening(false);
      };

      recognitionInstance.onerror = (event) => {
        console.error('音声認識エラー:', event.error);
        setIsListening(false);
        setRecognizedText('認識できませんでした');
      };

      recognitionInstance.onend = () => {
        setIsListening(false);
      };

      setRecognition(recognitionInstance);
    }
  }, [onAnswer]);

  const startListening = useCallback(() => {
    if (recognition && !isListening) {
      setRecognizedText('');
      setIsListening(true);
      recognition.start();
    }
  }, [recognition, isListening]);

  const stopListening = useCallback(() => {
    if (recognition && isListening) {
      recognition.stop();
      setIsListening(false);
    }
  }, [recognition, isListening]);

  return {
    isListening,
    recognizedText,
    startListening,
    stopListening,
    isSupported
  };
};
