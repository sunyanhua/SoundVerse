import { useState, useRef, useEffect } from 'react';
import { Play, Pause, Share2, Volume2 } from 'lucide-react';

interface AudioPlayerProps {
  audioUrl: string;
  title: string;
  duration?: number;
  onShare?: () => void;
}

export default function AudioPlayer({ audioUrl, title, duration, onShare }: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(1);
  const [actualDuration, setActualDuration] = useState(duration || 0);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const audioRef = useRef<HTMLAudioElement>(null);

  // 当audioUrl变化时，重新加载音频
  useEffect(() => {
    console.log('AudioPlayer: URL changed to:', audioUrl);
    const audio = audioRef.current;
    if (!audio) {
      console.log('AudioPlayer: audio element not found');
      return;
    }
    if (!audioUrl) {
      console.log('AudioPlayer: audioUrl is empty');
      setError('音频URL为空');
      return;
    }

    // 重置播放器状态
    setIsPlaying(false);
    setCurrentTime(0);
    setError(null);
    setIsLoading(true);

    // 显式设置src并加载
    audio.src = audioUrl;
    audio.load();
    console.log('AudioPlayer: loading audio from:', audioUrl);
  }, [audioUrl]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateTime = () => setCurrentTime(audio.currentTime);
    const handleEnded = () => setIsPlaying(false);
    const handleLoadedMetadata = () => {
      if (!duration && audio.duration) {
        setActualDuration(audio.duration);
      }
      setIsLoading(false);
    };
    const handleCanPlay = () => {
      setIsLoading(false);
      setError(null);
    };
    const handleError = () => {
      console.error('音频加载错误:', audio.error);
      // 有些浏览器会因CORS触发error，但实际上音频可以播放
      if (audio.readyState >= 2) {
        // HAVE_CURRENT_DATA or higher, 可以播放
        setIsLoading(false);
      } else {
        setError('音频加载失败，请重试');
        setIsLoading(false);
      }
    };

    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('canplay', handleCanPlay);
    audio.addEventListener('error', handleError);

    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('canplay', handleCanPlay);
      audio.removeEventListener('error', handleError);
    };
  }, [duration]);

  const togglePlay = async () => {
    const audio = audioRef.current;
    if (!audio) {
      console.log('AudioPlayer: togglePlay - no audio element');
      return;
    }

    console.log('AudioPlayer: togglePlay - current state:', isPlaying, 'src:', audio.src, 'readyState:', audio.readyState);

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      try {
        setError(null);
        console.log('AudioPlayer: trying to play...');
        await audio.play();
        console.log('AudioPlayer: play success');
        setIsPlaying(true);
      } catch (err) {
        console.error('AudioPlayer: play failed:', err);
        setError('播放失败: ' + (err instanceof Error ? err.message : String(err)));
        setIsPlaying(false);
      }
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio) return;

    const time = parseFloat(e.target.value);
    audio.currentTime = time;
    setCurrentTime(time);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current;
    if (!audio) return;

    const vol = parseFloat(e.target.value);
    audio.volume = vol;
    setVolume(vol);
  };

  const handleShare = () => {
    if (onShare) {
      onShare();
    } else {
      navigator.clipboard.writeText(audioUrl);
      alert('分享链接已复制到剪贴板');
    }
  };

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // 测试音频URL是否可用
  useEffect(() => {
    if (!audioUrl) return;

    console.log('AudioPlayer: testing URL:', audioUrl);

    // 尝试预加载音频
    const testAudio = new Audio();
    testAudio.preload = "metadata";

    testAudio.addEventListener('loadedmetadata', () => {
      console.log('AudioPlayer: URL is valid, duration:', testAudio.duration);
      setError(null);  // 清除之前的错误
    });

    testAudio.addEventListener('canplay', () => {
      console.log('AudioPlayer: can play');
      setError(null);
    });

    // 某些浏览器会因CORS报error，但音频实际可播放
    testAudio.addEventListener('error', (e) => {
      console.log('AudioPlayer: test load error (may be CORS, but might still play):', e);
      // 不设置错误，让主音频元素决定
    });

    testAudio.src = audioUrl;
  }, [audioUrl]);

  return (
    <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-4 shadow-md border border-blue-100">
      <audio ref={audioRef} src={audioUrl} preload="metadata" />

      {error && (
        <div className="mb-3 text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
          {error}
          <div className="text-xs text-gray-500 mt-1 break-all">URL: {audioUrl}</div>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {/* 第一行：播放按钮、时间、音量 */}
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            disabled={isLoading || !!error}
            className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white p-2.5 rounded-full transition-all shadow-lg hover:shadow-xl disabled:cursor-not-allowed flex-shrink-0"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>

          {/* 时间显示 */}
          <div className="flex items-center gap-1 text-xs text-gray-500 flex-shrink-0">
            <span>{formatTime(currentTime)}</span>
            <span>/</span>
            <span>{formatTime(actualDuration)}</span>
          </div>

          {/* 音量控制 */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <Volume2 className="w-3.5 h-3.5 text-gray-400" />
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={volume}
              onChange={handleVolumeChange}
              className="w-16 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
            />
          </div>
        </div>

        {/* 第二行：进度条单独一行 */}
        <div className="w-full">
          <input
            type="range"
            min="0"
            max={actualDuration}
            value={currentTime}
            onChange={handleSeek}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
          />
        </div>
      </div>
    </div>
  );
}
