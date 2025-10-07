import React, { useRef, useState } from 'react';
import { Volume2, VolumeX, RotateCcw } from 'lucide-react';

const AudioPlayer = ({ audioSrc, autoPlay = false }) => {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const playAudio = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const toggleMute = () => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
  };

  React.useEffect(() => {
    if (autoPlay && audioRef.current) {
      playAudio();
    }
  }, [audioSrc, autoPlay]);

  return (
    <div className="flex items-center gap-2">
      <audio
        ref={audioRef}
        src={audioSrc}
        onEnded={handleEnded}
        preload="auto"
      />
      
      <button
        onClick={playAudio}
        className="bg-blue-500 text-white p-2 rounded-lg hover:bg-blue-600 transition flex items-center gap-2"
        title="問題を読み上げる"
      >
        <RotateCcw className="w-4 h-4" />
        <span className="text-sm">もう一度聞く</span>
      </button>

      <button
        onClick={toggleMute}
        className="p-2 rounded-lg hover:bg-gray-200 transition"
        title={isMuted ? "音声をオン" : "音声をミュート"}
      >
        {isMuted ? (
          <VolumeX className="w-4 h-4 text-gray-600" />
        ) : (
          <Volume2 className="w-4 h-4 text-gray-600" />
        )}
      </button>

      {isPlaying && (
        <div className="flex items-center gap-1">
          <div className="w-1 h-3 bg-blue-500 animate-pulse rounded"></div>
          <div className="w-1 h-4 bg-blue-500 animate-pulse rounded animation-delay-100"></div>
          <div className="w-1 h-3 bg-blue-500 animate-pulse rounded animation-delay-200"></div>
        </div>
      )}
    </div>
  );
};

export default AudioPlayer;
