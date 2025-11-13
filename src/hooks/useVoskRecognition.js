import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Vosk音声認識用カスタムフック（常時認識モード）
 * マイクから音声を取得し、WebSocket経由でバックエンドに送信
 */
export const useVoskRecognition = (onAnswer, websocketUrl = 'ws://localhost:8000/ws') => {
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
        if (audioChunkCountRef.current % 50 === 0) {
          console.log(`📤 音声データ送信: ${audioChunkCountRef.current}チャンク目`);
          setDebugInfo(`送信: ${audioChunkCountRef.current}チャンク`);
        }
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
      console.log('🔌 WebSocket接続を試みています...');
      const ws = new WebSocket(websocketUrl);
      
      ws.onopen = () => {
        console.log('✅ Vosk WebSocket接続が確立されました');
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
            console.log(`📝 完全認識: ${data.text}`);
            setDebugInfo(`認識: ${data.text}`);
          }
          
          // 回答が検出された場合
          if (data.is_final && data.answer !== null && data.answer !== undefined) {
            console.log(`✓ 回答検出: ${data.answer ? 'まる' : 'ばつ'}`);
            onAnswer(data.answer);
            setRecognizedText('');
          }
        } else if (data.type === 'speech_error') {
          console.error('音声認識エラー:', data.error);
          setDebugInfo(`エラー: ${data.error}`);
        }
      };
      
      ws.onerror = (error) => {
        console.error('❌ WebSocketエラー:', error);
        setDebugInfo('WebSocketエラー');
      };
      
      ws.onclose = () => {
        console.log('🔌 WebSocket接続が切断されました');
        setIsConnected(false);
        setDebugInfo('切断');
        
        // 5秒後に再接続を試みる
        if (shouldRestartRef.current) {
          setTimeout(() => {
            if (shouldRestartRef.current) {
              console.log('🔄 WebSocket再接続を試みます...');
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
      console.log('ℹ️ 音声認識は既に実行中です');
      return;
    }

    try {
      console.log('🎤 マイクアクセスを要求しています...');
      
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
      console.log('✅ マイクアクセス許可');
      
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
      setDebugInfo('認識中');
      console.log('✅ 音声認識を開始しました（常時モード）');
      console.log(`サンプルレート: ${audioContext.sampleRate}Hz`);
      
    } catch (error) {
      console.error('❌ マイクアクセスエラー:', error);
      setIsSupported(false);
      setDebugInfo(`マイクエラー: ${error.message}`);
      
      // 5秒後に再試行
      if (autoStartEnabled && shouldRestartRef.current) {
        setTimeout(() => {
          if (shouldRestartRef.current) {
            console.log('🔄 マイクアクセスを再試行します...');
            startListening();
          }
        }, 5000);
      }
    }
  }, [processAudioData, autoStartEnabled]);

  // マイク入力を停止
  const stopListening = useCallback(() => {
    console.log('⏹️ 音声認識を停止しています...');
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
    console.log('✅ 音声認識を停止しました');
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
    }
    
    // WebSocket接続
    connectWebSocket();
    
    // 少し遅延してから自動的に音声認識を開始
    const autoStartTimer = setTimeout(() => {
      if (autoStartEnabled && shouldRestartRef.current) {
        console.log('🚀 音声認識を自動起動します...');
        startListening();
      }
    }, 2000);
    
    // クリーンアップ
    return () => {
      clearTimeout(autoStartTimer);
      shouldRestartRef.current = false;
      stopListening();
      
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket, startListening, stopListening, autoStartEnabled]);

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
