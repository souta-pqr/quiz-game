import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Vosk音声認識用カスタムフック（Silero VAD統合）
 * マイクから音声を取得し、WebSocket経由でバックエンド（Vosk + VAD）に送信して「まる」「ばつ」を検出
 */
export const useVoiceRecognition = (onAnswer, websocketUrl = 'ws://localhost:8000/ws/speech') => {
  const [isListening, setIsListening] = useState(false);
  const [recognizedText, setRecognizedText] = useState('');
  const [recognitionHistory, setRecognitionHistory] = useState([]);
  const [isSupported, setIsSupported] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [debugInfo, setDebugInfo] = useState('');
  const [autoStartEnabled, setAutoStartEnabled] = useState(true);
  
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const streamRef = useRef(null);
  const isActiveRef = useRef(true);
  const audioChunkCountRef = useRef(0);
  const shouldRestartRef = useRef(true);

  // 音声データを処理してバックエンドに送信
  const processAudioData = useCallback((audioData) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        // 16kHz, 16-bit PCMに変換
        const pcmData = convertTo16kHzPCM(audioData);
        wsRef.current.send(pcmData);
        audioChunkCountRef.current++;
      } catch (error) {
        console.error('音声データ送信エラー:', error);
        setDebugInfo(`送信エラー: ${error.message}`);
      }
    }
  }, []);

  // 音声データを16kHz, 16-bit PCMに変換
  const convertTo16kHzPCM = (audioData) => {
    const sampleRate = audioContextRef.current?.sampleRate || 48000;
    const targetSampleRate = 16000;
    
    // リサンプリング
    const ratio = sampleRate / targetSampleRate;
    const newLength = Math.round(audioData.length / ratio);
    const result = new Float32Array(newLength);
    
    for (let i = 0; i < newLength; i++) {
      const index = Math.floor(i * ratio);
      result[i] = audioData[index];
    }
    
    // 16-bit PCMに変換
    const buffer = new ArrayBuffer(result.length * 2);
    const view = new DataView(buffer);
    
    for (let i = 0; i < result.length; i++) {
      const s = Math.max(-1, Math.min(1, result[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    
    return buffer;
  };

  // WebSocket接続を確立
  const connectWebSocket = useCallback(() => {
    try {
      const ws = new WebSocket(websocketUrl);
      
      ws.onopen = () => {
        setIsConnected(true);
        setDebugInfo('接続成功');
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'speech_result') {
          const timestamp = new Date().toLocaleTimeString();
          
          // 認識結果を履歴に追加
          setRecognitionHistory(prev => [
            ...prev,
            {
              text: data.text,
              isFinal: data.is_final,
              answer: data.answer,
              timestamp
            }
          ].slice(-10)); // 最新10件のみ保持
          
          // 現在の認識テキストを更新
          setRecognizedText(data.text);
          
          if (data.is_final) {
            setDebugInfo(`認識: ${data.text}`);
          }
          
          // 回答が検出された場合
          if (data.is_final && data.answer !== null && data.answer !== undefined) {
            onAnswer(data.answer);
            setRecognizedText('');
          }
        } else if (data.type === 'speech_error') {
          console.error('音声認識エラー:', data.error);
          setDebugInfo(`エラー: ${data.error}`);
        } else if (data.type === 'pong') {
          // pongは無視
        } else {
          console.warn('不明なメッセージタイプ:', data.type);
        }
      };
      
      ws.onerror = (error) => {
        console.error('❌ WebSocketエラー:', error);
        setDebugInfo('WebSocketエラー');
      };
      
      ws.onclose = () => {
        setIsConnected(false);
        setDebugInfo('切断');
        
        // 5秒後に再接続を試みる
        if (shouldRestartRef.current) {
          setTimeout(() => {
            if (shouldRestartRef.current) {
              connectWebSocket();
            }
          }, 5000);
        }
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('❌ WebSocket接続エラー:', error);
      setDebugInfo(`接続エラー: ${error.message}`);
    }
  }, [websocketUrl, onAnswer]);

  // マイク入力を開始
  const startListening = useCallback(async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error('❌ このブラウザはマイク入力に対応していません');
      setIsSupported(false);
      setDebugInfo('マイク非対応');
      return;
    }

    // 既に起動中なら何もしない
    if (isActiveRef.current && audioContextRef.current) {
      return;
    }

    try {
      // マイクアクセスを要求
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 48000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        } 
      });
      
      streamRef.current = stream;
      setIsSupported(true);
      
      // AudioContextを作成
      const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 48000
      });
      audioContextRef.current = audioContext;
      
      const source = audioContext.createMediaStreamSource(stream);
      
      // ScriptProcessorNodeでリアルタイム処理
      // バッファサイズを4096に設定（約85msごとに処理）
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      
      processor.onaudioprocess = (e) => {
        if (isActiveRef.current) {
          const inputData = e.inputBuffer.getChannelData(0);
          processAudioData(inputData);
        }
      };
      
      source.connect(processor);
      processor.connect(audioContext.destination);
      
      audioChunkCountRef.current = 0;
      isActiveRef.current = true;
      setIsListening(true);
      setDebugInfo('認識中（VAD有効）');
      
    } catch (error) {
      console.error('❌ マイクアクセスエラー:', error);
      setIsSupported(false);
      setDebugInfo(`マイクエラー: ${error.message}`);
      
      // 5秒後に再試行
      if (autoStartEnabled && shouldRestartRef.current) {
        setTimeout(() => {
          if (shouldRestartRef.current) {
            startListening();
          }
        }, 5000);
      }
    }
  }, [processAudioData, autoStartEnabled]);

  // マイク入力を停止
  const stopListening = useCallback(() => {
    isActiveRef.current = false;
    
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    
    audioChunkCountRef.current = 0;
    setIsListening(false);
    setDebugInfo('停止');
  }, []);

  // 履歴をクリア
  const clearHistory = useCallback(() => {
    setRecognitionHistory([]);
    setDebugInfo('履歴クリア');
  }, []);

  // 初期化と自動起動
  useEffect(() => {
    // ブラウザ対応チェック
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      setIsSupported(true);
    } else {
      setIsSupported(false);
      console.warn('⚠️ このブラウザはマイク入力に対応していません');
      return;
    }
    
    // WebSocket接続
    connectWebSocket();
    
    // マウント時のフラグを設定
    let mounted = true;
    shouldRestartRef.current = true;
    
    // 少し遅延してから自動的に音声認識を開始
    const autoStartTimer = setTimeout(() => {
      if (mounted && autoStartEnabled && shouldRestartRef.current) {
        startListening();
      }
    }, 2000);
    
    // クリーンアップ
    return () => {
      mounted = false;
      clearTimeout(autoStartTimer);
      shouldRestartRef.current = false;
      stopListening();
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return {
    isListening,
    recognizedText,
    recognitionHistory,
    startListening,
    stopListening,
    clearHistory,
    isSupported,
    isConnected,
    debugInfo
  };
};
