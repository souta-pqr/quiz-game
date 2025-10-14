import { useState, useEffect, useCallback, useRef } from 'react';

export const useObjectDetection = (onPlayAudio) => {
  const [isConnected, setIsConnected] = useState(false);
  const [personDetected, setPersonDetected] = useState(false);
  const [detectionCount, setDetectionCount] = useState(0);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket('ws://localhost:8000/ws');
      
      ws.onopen = () => {
        console.log('物体検出サーバーに接続しました');
        setIsConnected(true);
        
        // Keep-alive ping
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
        
        ws.pingInterval = pingInterval;
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('受信:', data);
        
        if (data.type === 'person_detected') {
          setPersonDetected(true);
          setDetectionCount(data.count);
        } else if (data.type === 'play_audio') {
          console.log('音声再生トリガーを受信しました');
          setPersonDetected(false);
          if (onPlayAudio) {
            onPlayAudio();
          }
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocketエラー:', error);
      };
      
      ws.onclose = () => {
        console.log('WebSocket接続が切断されました');
        setIsConnected(false);
        setPersonDetected(false);
        
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval);
        }
        
        // 5秒後に再接続を試みる
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('再接続を試みます...');
          connect();
        }, 5000);
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('WebSocket接続エラー:', error);
    }
  }, [onPlayAudio]);

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
