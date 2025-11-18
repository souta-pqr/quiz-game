import React from 'react';

const ScoreBoard = ({ score, currentQuestion }) => {
  return (
    <div className="flex justify-between items-center mb-4">
      <h1 className="text-2xl font-bold text-red-700 flex items-center gap-2">
        🎄 ○×クイズ 🎅
      </h1>
      <div className="bg-gradient-to-r from-red-100 to-green-100 px-4 py-2 rounded-lg border-2 border-red-400 shadow-md">
        <span className="text-red-800 font-bold">
          ⭐ スコア: {score} / {currentQuestion}
        </span>
      </div>
    </div>
  );
};

export default ScoreBoard;
