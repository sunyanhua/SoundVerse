import { useState, useEffect } from 'react';
import { Search, Filter, Tag, Clock, Trash2 } from 'lucide-react';
import { supabase, AudioClip } from '../lib/supabase';
import { useAuth } from '../contexts/AuthContext';
import AudioPlayer from '../components/AudioPlayer';

export default function Library() {
  const { user } = useAuth();
  const [clips, setClips] = useState<AudioClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEmotion, setSelectedEmotion] = useState<string>('');
  const [selectedTag, setSelectedTag] = useState<string>('');

  const emotions = ['全部', '开心', '惊喜', '平静', '兴奋', '期待', '满足'];
  const allTags = ['生活', '北京', '美食', '天气', '日常', '心情', '旅行', '学习'];

  useEffect(() => {
    loadClips();
  }, [user]);

  const loadClips = async () => {
    if (!user) return;

    setLoading(true);
    const { data, error } = await supabase
      .from('audio_clips')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: false });

    if (error) {
      console.error('Error loading clips:', error);
    } else {
      setClips(data || []);
    }
    setLoading(false);
  };

  const deleteClip = async (id: string) => {
    if (!confirm('确定要删除这条语弹吗？')) return;

    const { error } = await supabase
      .from('audio_clips')
      .delete()
      .eq('id', id);

    if (error) {
      console.error('Error deleting clip:', error);
    } else {
      setClips(clips.filter(clip => clip.id !== id));
    }
  };

  const filteredClips = clips.filter(clip => {
    const matchesSearch = clip.transcription.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         clip.title.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesEmotion = !selectedEmotion || selectedEmotion === '全部' || clip.emotion === selectedEmotion;
    const matchesTag = !selectedTag || clip.tags.includes(selectedTag);

    return matchesSearch && matchesEmotion && matchesTag;
  });

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
          <div className="grid grid-cols-1 gap-4">
            {filteredClips.map((clip) => (
              <div
                key={clip.id}
                className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-800 mb-1">{clip.title}</h3>
                    <p className="text-gray-600 text-sm mb-3">{clip.transcription}</p>

                    <div className="flex flex-wrap gap-2 mb-3">
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                        {clip.emotion}
                      </span>
                      {clip.tags.map((tag, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
                        >
                          <Tag className="w-3 h-3 mr-1" />
                          {tag}
                        </span>
                      ))}
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                        <Clock className="w-3 h-3 mr-1" />
                        {clip.duration}秒
                      </span>
                    </div>
                  </div>

                  <button
                    onClick={() => deleteClip(clip.id)}
                    className="text-red-500 hover:text-red-700 p-2 hover:bg-red-50 rounded-lg transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>

                <AudioPlayer
                  audioUrl={clip.audio_url}
                  title={clip.title}
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

        {filteredClips.length > 0 && (
          <div className="mt-6 text-center text-gray-600">
            共 {filteredClips.length} 条语弹片段
            {(searchTerm || selectedEmotion || selectedTag) && ` (已筛选)`}
          </div>
        )}
      </div>
    </div>
  );
}
