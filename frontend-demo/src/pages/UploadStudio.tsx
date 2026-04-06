import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import { Upload, Sparkles, Check, Loader2 } from 'lucide-react';

const slicingStrategies = [
  { id: 'sentence', label: '短句裁切', description: '识别完整短句，生成简洁清晰的语弹片段' },
  { id: 'paragraph', label: '段落裁切', description: '按照语义段落分割，保持内容完整性' },
  { id: 'dialogue', label: '对话裁切', description: '智能识别对话场景，精准分割问答内容' },
];

export default function UploadStudio() {
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

  // 清理定时器
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

  // 检查处理状态
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
        alert(`音频处理失败: ${data.error_message || '请重试'}`);
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

    // 清理之前的定时器
    clearIntervals();

    setProcessing(true);
    setProgress(0);
    setIsComplete(false);
    setStatusMessage('正在上传音频...');

    try {
      // 创建 FormData
      const formData = new FormData();
      formData.append('audio_file', selectedFile);
      formData.append('title', selectedFile.name.replace(/\.[^/.]+$/, ''));
      formData.append('program_type', 'upload');
      formData.append('is_public', 'true');
      formData.append('slicing_strategy', selectedStrategy);

      // 上传音频
      const response = await api.upload('/v1/audio/upload', formData);
      const data = response as { upload_id: string };

      if (!data.upload_id) {
        throw new Error('上传失败，未返回 upload_id');
      }

      setUploadId(data.upload_id);
      setStatusMessage('上传成功，开始 AI 处理...');

      // 模拟进度动画（到90%）
      progressIntervalRef.current = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            return prev;
          }
          return prev + Math.random() * 5;
        });
      }, 1000);

      // 开始轮询处理状态
      statusCheckIntervalRef.current = setInterval(() => {
        checkProcessingStatus(data.upload_id);
      }, 3000);

      // 立即检查一次
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

  return (
    <div className="min-h-full bg-gradient-to-br from-blue-50 via-white to-purple-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">音频工坊</h1>
          <p className="text-gray-600">上传音频文件，AI 智能裁切成精彩语弹片段</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8 mb-6">
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

          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              选择裁切策略
            </label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {slicingStrategies.map((strategy) => (
                <button
                  key={strategy.id}
                  onClick={() => setSelectedStrategy(strategy.id)}
                  className={`p-4 rounded-xl border-2 transition-all text-left ${
                    selectedStrategy === strategy.id
                      ? 'border-blue-500 bg-blue-50 shadow-md'
                      : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-semibold text-gray-800">{strategy.label}</h3>
                    {selectedStrategy === strategy.id && (
                      <Check className="w-5 h-5 text-blue-500" />
                    )}
                  </div>
                  <p className="text-sm text-gray-600">{strategy.description}</p>
                </button>
              ))}
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
                    已成功生成 {segmentsCount} 个语弹片段，请前往"精选语弹库"查看
                  </p>
                </div>
              </div>
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
              <span className="mr-2">🎯</span>
              <span>根据您选择的策略，生成长度适中、语义完整的语弹片段</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">🏷️</span>
              <span>自动为每个片段添加情绪标签和内容标签，方便后续检索</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
