import { useState } from 'react';
import { Upload, Sparkles, Check, Loader2 } from 'lucide-react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../contexts/AuthContext';

const slicingStrategies = [
  { id: 'sentence', label: '短句裁切', description: '识别完整短句，生成简洁清晰的语弹片段' },
  { id: 'paragraph', label: '段落裁切', description: '按照语义段落分割，保持内容完整性' },
  { id: 'dialogue', label: '对话裁切', description: '智能识别对话场景，精准分割问答内容' },
];

const mockTranscriptions = [
  '今天北京的天气真不错，阳光明媚，温度适宜',
  '刚才在路上看到了一只可爱的小狗，忍不住多看了几眼',
  '这个餐厅的烤鸭真是太好吃了，皮脆肉嫩，回味无穷',
  '早高峰的地铁真是太挤了，但大家都很有秩序',
  '周末计划去颐和园走走，呼吸一下新鲜空气',
  '最近在学习一门新技能，感觉很有成就感',
];

const mockEmotions = ['开心', '惊喜', '平静', '兴奋', '期待', '满足'];
const mockTags = ['生活', '北京', '美食', '天气', '日常', '心情', '旅行', '学习'];

export default function UploadStudio() {
  const { user } = useAuth();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState('sentence');
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setIsComplete(false);
    }
  };

  const simulateProcessing = async () => {
    setProcessing(true);
    setProgress(0);
    setIsComplete(false);

    for (let i = 0; i <= 100; i += 2) {
      await new Promise(resolve => setTimeout(resolve, 80));
      setProgress(i);
    }

    const clipsToGenerate = Math.floor(Math.random() * 3) + 4;
    const generatedClips = [];

    for (let i = 0; i < clipsToGenerate; i++) {
      const transcription = mockTranscriptions[Math.floor(Math.random() * mockTranscriptions.length)];
      const emotion = mockEmotions[Math.floor(Math.random() * mockEmotions.length)];
      const duration = Math.floor(Math.random() * 10) + 5;
      const randomTags = mockTags
        .sort(() => 0.5 - Math.random())
        .slice(0, Math.floor(Math.random() * 3) + 2);

      const { error } = await supabase.from('audio_clips').insert({
        user_id: user?.id,
        title: `${selectedFile?.name || '音频'} - 片段 ${i + 1}`,
        transcription,
        duration,
        audio_url: `https://example.com/audio/${Date.now()}_${i}.mp3`,
        tags: randomTags,
        emotion,
      });

      if (error) {
        console.error('Error creating clip:', error);
      }
    }

    setProcessing(false);
    setIsComplete(true);
  };

  const handleUpload = () => {
    if (selectedFile) {
      simulateProcessing();
    }
  };

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
                <span className="text-sm font-medium text-blue-600">{progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all duration-300 rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-sm text-gray-600 mt-3">
                正在分析音频特征、识别语义边界、生成语弹片段...
              </p>
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
                    已成功生成多个语弹片段，请前往"精选语弹库"查看
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
