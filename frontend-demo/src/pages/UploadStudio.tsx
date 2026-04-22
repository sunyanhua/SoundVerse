import { useState, useEffect, useRef } from 'react';
import { api, AudioSource } from '../lib/api';
import { Upload, Sparkles, Check, Loader2, Play, Pause, RotateCcw, Trash2, Music, Clock, FileAudio, ChevronLeft } from 'lucide-react';
import AudioPlayer from '../components/AudioPlayer';

const slicingStrategies = [
  { id: 'sentence', label: '短句裁切', description: '识别完整短句，生成简洁清晰的语弹片段' },
  { id: 'paragraph', label: '段落裁切', description: '按照语义段落分割，保持内容完整性' },
  { id: 'dialogue', label: '对话裁切', description: '智能识别对话场景，精准分割问答内容' },
];

export default function UploadStudio() {
  // 视图状态：'list' = 节目列表, 'upload' = 上传界面
  const [view, setView] = useState<'list' | 'upload'>('list');

  // 节目列表状态
  const [sources, setSources] = useState<AudioSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingSourceId, setPlayingSourceId] = useState<string | null>(null);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);

  // 上传状态
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState('sentence');
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState('准备处理...');
  const [segmentsCount, setSegmentsCount] = useState(0);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const statusCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 加载节目列表
  useEffect(() => {
    if (view === 'list') {
      loadSources();
    }
  }, [view]);

  // 定时刷新节目列表（当有处理中的节目时，每5秒刷新一次）
  useEffect(() => {
    if (view !== 'list') return;

    // 使用 ref 避免依赖 sources 导致频繁重置 interval
    const checkAndRefresh = () => {
      setSources(currentSources => {
        const hasProcessing = currentSources.some(
          s => s.processing_status === 'processing'
        );
        if (hasProcessing) {
          // 有处理中的任务，后台刷新（不显示 loading）
          loadSources(true);
        }
        return currentSources;
      });
    };

    // 立即检查一次
    checkAndRefresh();

    // 设置定时刷新
    const interval = setInterval(checkAndRefresh, 5000);
    return () => clearInterval(interval);
  }, [view]); // 只依赖 view，避免 sources 变化导致重置

  const loadSources = async (background = false) => {
    if (!background) {
      setLoading(true);
    }
    try {
      const response = await api.get<{ items: AudioSource[]; total: number }>('/v1/audio/sources');
      setSources(response?.items || []);
    } catch (error) {
      console.error('Error loading sources:', error);
    }
    if (!background) {
      setLoading(false);
    }
  };

  const handleDelete = async (sourceId: string) => {
    if (!confirm('确定要删除这个节目吗？这将清空该节目已经生成的所有语弹文件及数据。')) return;

    try {
      await api.delete(`/v1/audio/source/${sourceId}`);
      setSources(sources.filter(s => s.id !== sourceId));
    } catch (error) {
      console.error('Error deleting source:', error);
      alert('删除失败，请重试');
    }
  };

  const handleReprocess = async (sourceId: string) => {
    if (!confirm('确定要重新裁切这个节目吗？这将重新生成所有语弹片段。')) return;

    setReprocessingId(sourceId);
    try {
      await api.post(`/v1/audio/sources/${sourceId}/reprocess`);
      // 刷新列表以显示新的处理状态
      await loadSources();
    } catch (error) {
      console.error('Error reprocessing source:', error);
      alert('重新裁切失败，请重试');
    } finally {
      setReprocessingId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
            <Check className="w-3 h-3 mr-1" />
            已完成
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            裁切中
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
            <Clock className="w-3 h-3 mr-1" />
            等待中
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
            失败
          </span>
        );
      default:
        return null;
    }
  };

  const formatDuration = (seconds: number) => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // 上传相关函数
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setIsComplete(false);
      setUploadId(null);
      setProgress(0);
      setSegmentsCount(0);
    }
  };

  const clearIntervals = () => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
    if (statusCheckIntervalRef.current) {
      clearInterval(statusCheckIntervalRef.current);
      statusCheckIntervalRef.current = null;
    }
  };

  const checkProcessingStatus = async (id: string) => {
    try {
      const response = await api.get(`/v1/audio/processing/${id}`);
      const data = response as {
        status: string;
        progress: number;
        error_message?: string;
        result?: { segments_count: number };
      };

      setProgress(Math.min(data.progress * 100, 99));
      setStatusMessage(getStatusText(data.status));

      if (data.status === 'completed') {
        clearIntervals();
        setProgress(100);
        setIsComplete(true);
        setProcessing(false);
        setSegmentsCount(data.result?.segments_count || 0);
      } else if (data.status === 'failed') {
        clearIntervals();
        setProcessing(false);
        setStatusMessage(`处理失败: ${data.error_message || '未知错误'}`);
        // 不显示弹窗，用户可以在节目列表中看到失败状态并继续其他操作
      }
    } catch (error) {
      console.error('检查处理状态失败:', error);
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '等待处理...';
      case 'processing':
        return 'AI 正在分析音频特征、识别语义边界...';
      case 'completed':
        return '处理完成！';
      case 'failed':
        return '处理失败';
      default:
        return '处理中...';
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    clearIntervals();
    setProcessing(true);
    setProgress(0);
    setIsComplete(false);
    setStatusMessage('正在上传音频...');

    try {
      const formData = new FormData();
      formData.append('audio_file', selectedFile);
      formData.append('title', selectedFile.name.replace(/\.[^/.]+$/, ''));
      formData.append('program_type', 'upload');
      formData.append('is_public', 'true');
      formData.append('slicing_strategy', selectedStrategy);

      const response = await api.upload('/v1/audio/upload', formData);
      const data = response as { upload_id: string };

      if (!data.upload_id) {
        throw new Error('上传失败，未返回 upload_id');
      }

      setUploadId(data.upload_id);
      setStatusMessage('上传成功，开始 AI 处理...');

      progressIntervalRef.current = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            return prev;
          }
          return prev + Math.random() * 5;
        });
      }, 1000);

      statusCheckIntervalRef.current = setInterval(() => {
        checkProcessingStatus(data.upload_id);
      }, 3000);

      checkProcessingStatus(data.upload_id);

    } catch (error) {
      console.error('Upload error:', error);
      clearIntervals();
      setProcessing(false);
      alert('上传失败，请重试');
    }
  };

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      clearIntervals();
    };
  }, []);

  // 当切换到上传视图时，如果有未完成的处理任务，恢复轮询
  useEffect(() => {
    if (view === 'upload' && uploadId && processing && !isComplete) {
      // 恢复状态检查轮询
      if (!statusCheckIntervalRef.current) {
        statusCheckIntervalRef.current = setInterval(() => {
          checkProcessingStatus(uploadId);
        }, 3000);
      }
      // 立即检查一次
      checkProcessingStatus(uploadId);
    }
  }, [view]);

  // 渲染节目列表视图
  const renderListView = () => (
    <>
      {/* 标题和上传按钮 */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">音频工坊</h1>
          <p className="text-gray-600">管理你的音频节目，AI 智能裁切成精彩语弹片段</p>
        </div>
        <button
          onClick={() => setView('upload')}
          className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-semibold px-6 py-3 rounded-xl transition-all shadow-lg hover:shadow-xl flex items-center"
        >
          <Upload className="w-5 h-5 mr-2" />
          上传新节目
        </button>
      </div>

      {/* 节目列表 */}
      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
          <p className="text-gray-600 mt-4">加载中...</p>
        </div>
      ) : sources.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
          <FileAudio className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-800 mb-2">还没有节目</h3>
          <p className="text-gray-600 mb-6">上传你的第一个音频文件，让 AI 帮你裁切成精彩语弹</p>
          <button
            onClick={() => setView('upload')}
            className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-semibold px-6 py-3 rounded-xl transition-all shadow-lg hover:shadow-xl inline-flex items-center"
          >
            <Upload className="w-5 h-5 mr-2" />
            上传新节目
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {sources.map((source) => (
            <div
              key={source.id}
              className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow p-5"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <Music className="w-5 h-5 text-purple-500" />
                    <h3 className="font-semibold text-gray-800 text-lg">{source.title}</h3>
                  </div>

                  <div className="flex flex-wrap gap-2 mb-3">
                    {getStatusBadge(source.processing_status)}
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                      <Clock className="w-3 h-3 mr-1" />
                      {formatDuration(source.duration)}
                    </span>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                      {source.segments_count} 个语弹
                    </span>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                      {source.format.toUpperCase()}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleReprocess(source.id)}
                    disabled={reprocessingId === source.id || source.processing_status === 'processing'}
                    className="text-blue-500 hover:text-blue-700 p-2 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50"
                    title="重新裁切"
                  >
                    {reprocessingId === source.id ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <RotateCcw className="w-5 h-5" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(source.id)}
                    className="text-red-500 hover:text-red-700 p-2 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除节目"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* 音频播放器 */}
              {source.audio_url && source.processing_status !== 'pending' && (
                <AudioPlayer
                  audioUrl={source.audio_url}
                  title={source.title}
                  duration={source.duration}
                  onShare={() => {
                    navigator.clipboard.writeText(`分享节目：${source.title}`);
                    alert('分享链接已复制到剪贴板');
                  }}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {sources.length > 0 && (
        <div className="mt-6 text-center text-gray-600">
          共 {sources.length} 个节目
        </div>
      )}
    </>
  );

  // 渲染上传视图
  const renderUploadView = () => (
    <>
      {/* 返回按钮 */}
      <button
        onClick={() => setView('list')}
        className="mb-6 text-gray-600 hover:text-gray-800 flex items-center transition-colors"
      >
        <ChevronLeft className="w-5 h-5 mr-1" />
        返回节目列表
      </button>

      <div className="bg-white rounded-2xl shadow-xl p-8 mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">上传新节目</h2>

        <div className="mb-6">
          <label className="block text-sm font-semibold text-gray-700 mb-3">
            选择音频文件
          </label>
          <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors cursor-pointer bg-gray-50">
            <input
              type="file"
              accept="audio/*"
              onChange={handleFileSelect}
              className="hidden"
              id="audio-upload"
            />
            <label htmlFor="audio-upload" className="cursor-pointer">
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-600 font-medium">
                {selectedFile ? selectedFile.name : '点击上传或拖拽音频文件到这里'}
              </p>
              <p className="text-sm text-gray-400 mt-2">
                支持 MP3, WAV, M4A 等格式
              </p>
            </label>
          </div>
        </div>

        {processing && (
          <div className="mb-6 bg-blue-50 rounded-xl p-6 border border-blue-100">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center">
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin mr-2" />
                <span className="font-semibold text-gray-800">AI 智能处理中...</span>
              </div>
              <span className="text-sm font-medium text-blue-600">{Math.round(progress)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all duration-300 rounded-full"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
            <p className="text-sm text-gray-600 mt-3">{statusMessage}</p>
          </div>
        )}

        {isComplete && (
          <div className="mb-6 bg-green-50 rounded-xl p-6 border border-green-200">
            <div className="flex items-center">
              <div className="bg-green-500 rounded-full p-2 mr-3">
                <Check className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-800">处理完成！</h3>
                <p className="text-sm text-gray-600">
                  已成功生成 {segmentsCount} 个语弹片段
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                setView('list');
                loadSources();
              }}
              className="mt-4 text-blue-600 hover:text-blue-800 font-medium"
            >
              返回节目列表查看 →
            </button>
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={!selectedFile || processing}
          className="w-full bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-semibold py-4 rounded-xl transition-all shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          <Sparkles className="w-5 h-5 mr-2" />
          {processing ? '处理中...' : '开始 AI 智能裁切'}
        </button>
      </div>

      <div className="bg-gradient-to-r from-blue-500 to-purple-500 rounded-2xl p-6 text-white shadow-xl">
        <h3 className="font-bold text-lg mb-3">智能裁切说明</h3>
        <ul className="space-y-2 text-sm">
          <li className="flex items-start">
            <span className="mr-2">✨</span>
            <span>AI 会自动识别音频中的有效内容，过滤噪音和无效片段</span>
          </li>
          <li className="flex items-start">
            <span className="mr-2">⏱️</span>
            <span>文件上传成功后，将在后台运行智能裁切，您可以返回节目列表查看语弹数量变化</span>
          </li>
          <li className="flex items-start">
            <span className="mr-2">🏷️</span>
            <span>自动为每个片段添加情绪标签和内容标签，方便后续检索</span>
          </li>
        </ul>
      </div>
    </>
  );

  return (
    <div className="min-h-full bg-gradient-to-br from-purple-50 via-white to-blue-50 p-6">
      <div className="max-w-4xl mx-auto">
        {view === 'list' ? renderListView() : renderUploadView()}
      </div>
    </div>
  );
}
