import React from 'react';

const MotorProcessingOverlay = ({ isVisible }) => {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full mx-4 text-center">
        {/* スピナー */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
        </div>
        
        {/* メッセージ */}
        <h2 className="text-2xl font-bold text-gray-800 mb-2">
          モータ動作中
        </h2>
        <p className="text-gray-600">
          次の回答者を選ぶための動作です...
        </p>
      </div>
    </div>
  );
};

export default MotorProcessingOverlay;
