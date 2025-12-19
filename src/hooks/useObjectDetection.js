import { useState, useEffect, useCallback, useRef } from 'react';

export const useObjectDetection = (onPlayAudio, onPersonSelected, onMotorProcessing) => {
  const [isConnected, setIsConnected] = useState(false);
  const [personDetected, setPersonDetected] = useState(false);
  const [detectionCount, setDetectionCount] = useState(0);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket('ws://localhost:8000/ws/detection');
      
      ws.onopen = () => {
        console.log('✓ 物体検出WebSocket接続');
        setIsConnected(true);
        
        // Keep-alive ping（60秒に延長して負荷軽減）
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 60000);
        
        ws.pingInterval = pingInterval;
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'person_detected') {
          // 人検出中（モーター停止前）
          setPersonDetected(true);
          setDetectionCount(data.count);
        } else if (data.type === 'person_selected') {
          // 人選択確定（モーター停止、画像あり）
          console.log('👤 回答者選択確定:', data);
          setPersonDetected(false);
          
          // 回答者画像を親コンポーネントに渡す
          if (onPersonSelected && data.snapshot) {
            onPersonSelected(data.snapshot);
          }
          
          // 音声再生トリガー
          if (onPlayAudio) {
            onPlayAudio();
          }
        } else if (data.type === 'play_audio') {
          // 従来の音声再生トリガー（後方互換性）
          setPersonDetected(false);
          if (onPlayAudio) {
            onPlayAudio();
          }
        } else if (data.type === 'motor_processing') {
          // モーター処理状態の通知
          if (onMotorProcessing) {
            onMotorProcessing(data.status);
          }
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocketエラー:', error);
      };
      
      ws.onclose = () => {
        console.log('✗ 物体検出WebSocket切断');
        setIsConnected(false);
        setPersonDetected(false);
        
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval);
        }
        
        // 5秒後に再接続を試みる
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('🔄 物体検出WebSocket再接続中...');
          connect();
        }, 5000);
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('WebSocket接続エラー:', error);
    }
  }, [onPlayAudio, onPersonSelected, onMotorProcessing]);

  useEffect(() => {
    connect();
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    isConnected,
    personDetected,
    detectionCount
  };
};
