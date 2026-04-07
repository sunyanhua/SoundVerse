import { useState, useEffect } from 'react';
import { Search, Filter, Tag, Clock, Trash2, Music, ChevronDown, ChevronRight } from 'lucide-react';
import { api, AudioClip } from '../lib/api';
import AudioPlayer from '../components/AudioPlayer';

// 清洗转录文本，移除前缀和多余内容
function cleanTranscription(text: string): string {
  if (!text) return '';
  // 移除"人声转录："前缀
  text = text.replace(/^人声转录[：:]\s*/g, '');
  // 移除其他可能的前缀
  text = text.replace(/^(原文|转录|识别)[：:]\s*/g, '');
  // 限制长度，最多显示 100 个字符
  if (text.length > 100) {
    text = text.substring(0, 100) + '...';
  }
  return text.trim();
}

interface GroupedClips {
  [sourceTitle: string]: AudioClip[];
}

export default function Library() {
  const [clips, setClips] = useState<AudioClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEmotion, setSelectedEmotion] = useState<string>('');
  const [selectedTag, setSelectedTag] = useState<string>('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const emotions = ['全部', '开心', '惊喜', '平静', '兴奋', '期待', '满足'];
  const allTags = ['生活', '北京', '美食', '天气', '日常', '心情', '旅行', '学习'];

  useEffect(() => {
    loadClips();
  }, []);

  const loadClips = async () => {
    setLoading(true);
    try {
      const response = await api.get<{ data: AudioClip[]; total: number }>('/v1/audio/segments?limit=100');
      setClips(response?.data || []);
    } catch (error) {
      console.error('Error loading clips:', error);
      setClips([]);
    }
    setLoading(false);
  };

  const deleteClip = async (id: string) => {
    if (!confirm('确定要删除这条语弹吗？')) return;

    try {
      await api.delete(`/v1/audio/favorite/${id}`);
      setClips(clips.filter(clip => clip.id !== id));
    } catch (error) {
      console.error('Error deleting clip:', error);
    }
  };

  const filteredClips = clips.filter(clip => {
    const matchesSearch = clip.transcription.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         clip.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesEmotion = !selectedEmotion || selectedEmotion === '全部' || clip.emotion === selectedEmotion;
    const matchesTag = !selectedTag || clip.tags.includes(selectedTag);

    return matchesSearch && matchesEmotion && matchesTag;
  });

  // 按来源分组
  const groupedClips: GroupedClips = filteredClips.reduce((groups, clip) => {
    const sourceTitle = clip.source_title || '未分类节目';
    if (!groups[sourceTitle]) {
      groups[sourceTitle] = [];
    }
    groups[sourceTitle].push(clip);
    return groups;
  }, {} as GroupedClips);

  // 默认展开所有分组
  useEffect(() => {
    const allTitles = Object.keys(groupedClips);
    setExpandedGroups(new Set(allTitles));
  }, [clips, searchTerm, selectedEmotion, selectedTag]);

  const toggleGroup = (sourceTitle: string) => {
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sourceTitle)) {
        newSet.delete(sourceTitle);
      } else {
        newSet.add(sourceTitle);
      }
      return newSet;
    });
  };

  return (
    <div className="min-h-full bg-gradient-to-br from-purple-50 via-white to-blue-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">精选语弹库</h1>
          <p className="text-gray-600">管理和浏览你的所有音频片段</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="搜索语弹内容..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="flex gap-3">
              <select
                value={selectedEmotion}
                onChange={(e) => setSelectedEmotion(e.target.value)}
                className="px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
              >
                {emotions.map(emotion => (
                  <option key={emotion} value={emotion === '全部' ? '' : emotion}>
                    {emotion}
                  </option>
                ))}
              </select>

              <select
                value={selectedTag}
                onChange={(e) => setSelectedTag(e.target.value)}
                className="px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
              >
                <option value="">所有标签</option>
                {allTags.map(tag => (
                  <option key={tag} value={tag}>{tag}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
            <p className="text-gray-600 mt-4">加载中...</p>
          </div>
        ) : filteredClips.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
            <Filter className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-800 mb-2">
              {clips.length === 0 ? '还没有语弹片段' : '没有找到匹配的语弹'}
            </h3>
            <p className="text-gray-600">
              {clips.length === 0
                ? '前往"音频工坊"上传并裁切你的第一个音频文件'
                : '尝试调整搜索条件或筛选器'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6">
            {Object.entries(groupedClips).map(([sourceTitle, sourceClips]) => (
              <div key={sourceTitle} className="bg-white rounded-2xl shadow-lg overflow-hidden">
                {/* 分组标题 */}
                <button
                  onClick={() => toggleGroup(sourceTitle)}
                  className="w-full flex items-center justify-between p-5 bg-gradient-to-r from-indigo-50 to-purple-50 hover:from-indigo-100 hover:to-purple-100 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Music className="w-5 h-5 text-indigo-600" />
                    <h2 className="text-lg font-bold text-gray-800">{sourceTitle}</h2>
                    <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs rounded-full">
                      {sourceClips.length} 条语弹
                    </span>
                  </div>
                  {expandedGroups.has(sourceTitle) ? (
                    <ChevronDown className="w-5 h-5 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-500" />
                  )}
                </button>

                {/* 分组内容 */}
                {expandedGroups.has(sourceTitle) && (
                  <div className="p-4 space-y-4">
                    {sourceClips.map((clip) => (
                      <div
                        key={clip.id}
                        className="bg-gray-50 rounded-xl p-4 hover:shadow-md transition-shadow"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <p className="text-gray-700 text-sm mb-2 leading-relaxed">
                              {cleanTranscription(clip.transcription)}
                            </p>

                            <div className="flex flex-wrap gap-2">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                                {clip.emotion || '平静'}
                              </span>
                              {clip.tags?.map((tag, index) => (
                                <span
                                  key={index}
                                  className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
                                >
                                  <Tag className="w-3 h-3 mr-1" />
                                  {tag}
                                </span>
                              ))}
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                                <Clock className="w-3 h-3 mr-1" />
                                {clip.duration}秒
                              </span>
                            </div>
                          </div>

                          <button
                            onClick={() => deleteClip(clip.id)}
                            className="text-red-500 hover:text-red-700 p-2 hover:bg-red-50 rounded-lg transition-colors ml-2"
                            title="删除"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>

                        <AudioPlayer
                          audioUrl={clip.audio_url}
                          title={clip.title || '语弹片段'}
                          duration={clip.duration}
                          onShare={() => {
                            navigator.clipboard.writeText(`分享语弹：${clip.transcription}`);
                            alert('分享链接已复制到剪贴板');
                          }}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {filteredClips.length > 0 && (
          <div className="mt-6 text-center text-gray-600">
            共 {Object.keys(groupedClips).length} 个节目，{filteredClips.length} 条语弹片段
            {(searchTerm || selectedEmotion || selectedTag) && ` (已筛选)`}
          </div>
        )}
      </div>
    </div>
  );
}
