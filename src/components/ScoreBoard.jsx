import React from 'react';

const ScoreBoard = ({ score, currentQuestion }) => {
  return (
    <div className="flex justify-between items-center mb-4">
      <h1 className="text-2xl font-bold text-gray-800">○×クイズ</h1>
      <div className="bg-blue-100 px-4 py-2 rounded-lg">
        <span className="text-blue-800 font-semibold">
          スコア: {score} / {currentQuestion}
        </span>
      </div>
    </div>
  );
};

export default ScoreBoard;
