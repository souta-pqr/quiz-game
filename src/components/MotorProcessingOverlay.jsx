import React from 'react';
import { Settings, RefreshCw } from 'lucide-react';

const MotorProcessingOverlay = ({ isVisible }) => {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-70 animate-fade-in">
      {/* 背景装飾 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-10 left-10 text-8xl animate-bounce opacity-30">⚙️</div>
        <div className="absolute top-10 right-10 text-8xl animate-bounce opacity-30" style={{animationDelay: '0.2s'}}>🔧</div>
        <div className="absolute bottom-10 left-10 text-8xl animate-pulse opacity-30" style={{animationDelay: '0.4s'}}>🤖</div>
        <div className="absolute bottom-10 right-10 text-8xl animate-pulse opacity-30" style={{animationDelay: '0.6s'}}>🔄</div>
        <div className="absolute top-1/3 left-1/4 text-7xl animate-spin-slow opacity-20">⚙️</div>
        <div className="absolute top-2/3 right-1/4 text-7xl animate-spin-slow opacity-20" style={{animationDelay: '0.3s'}}>⚙️</div>
      </div>
      
      {/* メインコンテンツ */}
      <div className="relative z-10 bg-gradient-to-br from-blue-600 via-purple-600 to-blue-700 rounded-3xl shadow-2xl p-12 max-w-2xl w-full mx-4 border-8 border-yellow-400">
        {/* 装飾 */}
        <div className="absolute -top-6 left-1/2 transform -translate-x-1/2 text-7xl animate-bounce">
          🤖
        </div>
        <div className="absolute -top-4 left-8 text-5xl animate-spin-slow">⚙️</div>
        <div className="absolute -top-4 right-8 text-5xl animate-spin-slow" style={{animationDelay: '0.5s', animationDirection: 'reverse'}}>⚙️</div>
        
        {/* タイトル */}
        <div className="text-center mb-8">
          <h2 className="text-5xl font-black text-white mb-4 animate-pulse" style={{
            textShadow: '4px 4px 8px rgba(0,0,0,0.5)',
            WebkitTextStroke: '2px #FFD700'
          }}>
            モーター処理中
          </h2>
          <p className="text-2xl text-yellow-200 font-bold">
            次の回答者を選んでいます...
          </p>
        </div>
        
        {/* ローディングアニメーション */}
        <div className="flex items-center justify-center gap-8 mb-8">
          {/* 回転する歯車 */}
          <div className="relative">
            <Settings className="w-24 h-24 text-yellow-400 animate-spin" style={{animationDuration: '2s'}} />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 bg-white rounded-full animate-pulse"></div>
            </div>
          </div>
          
          {/* 矢印 */}
          <div className="flex flex-col gap-2">
            <div className="text-6xl animate-bounce">➡️</div>
            <div className="text-xs text-yellow-200 font-bold text-center">CW/CCW</div>
          </div>
          
          {/* 反対方向に回転する歯車 */}
          <div className="relative">
            <Settings className="w-24 h-24 text-yellow-400 animate-spin-reverse" style={{animationDuration: '1.5s'}} />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 bg-white rounded-full animate-pulse" style={{animationDelay: '0.5s'}}></div>
            </div>
          </div>
        </div>
        
        {/* プログレスバー風アニメーション */}
        <div className="bg-white bg-opacity-30 rounded-full h-6 overflow-hidden mb-6">
          <div className="h-full bg-gradient-to-r from-yellow-400 via-green-400 to-yellow-400 rounded-full animate-progress"></div>
        </div>
        
        {/* 説明テキスト */}
        <div className="bg-white bg-opacity-20 rounded-2xl p-6 backdrop-blur-sm">
          <div className="flex items-center justify-center gap-3 mb-3">
            <RefreshCw className="w-6 h-6 text-yellow-300 animate-spin" />
            <p className="text-lg text-white font-bold">モーターがランダムに回転中</p>
            <RefreshCw className="w-6 h-6 text-yellow-300 animate-spin" style={{animationDirection: 'reverse'}} />
          </div>
          <p className="text-center text-yellow-100 text-sm">
            CW（時計回り）とCCW（反時計回り）を交互に<br />
            ランダムな時間で回転しています（約2〜3秒）
          </p>
        </div>
        
        {/* フッター装飾 */}
        <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 text-5xl">
          🔧
        </div>
        <div className="absolute -bottom-3 left-4 text-4xl animate-bounce">⚡</div>
        <div className="absolute -bottom-3 right-4 text-4xl animate-bounce" style={{animationDelay: '0.3s'}}>⚡</div>
      </div>
      
      {/* カスタムアニメーション用のスタイル */}
      <style>{`
        @keyframes spin-slow {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
        
        @keyframes spin-reverse {
          from {
            transform: rotate(360deg);
          }
          to {
            transform: rotate(0deg);
          }
        }
        
        @keyframes progress {
          0% {
            width: 0%;
          }
          50% {
            width: 100%;
          }
          100% {
            width: 0%;
          }
        }
        
        .animate-spin-slow {
          animation: spin-slow 3s linear infinite;
        }
        
        .animate-spin-reverse {
          animation: spin-reverse 1.5s linear infinite;
        }
        
        .animate-progress {
          animation: progress 2s ease-in-out infinite;
        }
        
        @keyframes fade-in {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
        
        .animate-fade-in {
          animation: fade-in 0.3s ease-in;
        }
      `}</style>
    </div>
  );
};

export default MotorProcessingOverlay;
