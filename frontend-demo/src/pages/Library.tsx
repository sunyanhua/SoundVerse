import { useState, useEffect, useMemo } from 'react';
import { Search, Filter, Tag, Clock, Trash2, Music, ChevronLeft, ChevronRight, Folder, Share2 } from 'lucide-react';
import { api, AudioClip } from '../lib/api';
import AudioPlayer from '../components/AudioPlayer';

// 清洗转录文本，移除前缀和多余内容
function cleanTranscription(text: string): string {
  if (!text) return '';
  text = text.replace(/^人声转录[：:]\s*/g, '');
  text = text.replace(/^(原文|转录|识别)[：:]\s*/g, '');
  if (text.length > 100) {
    text = text.substring(0, 100) + '...';
  }
  return text.trim();
}

// 根据情绪返回对应的颜色样式
function getEmotionStyles(emotion: string): string {
  const styles: Record<string, string> = {
    '开心': 'bg-yellow-100 text-yellow-700',
    '惊喜': 'bg-purple-100 text-purple-700',
    '平静': 'bg-blue-100 text-blue-700',
    '愤怒': 'bg-red-100 text-red-700',
    '恐惧': 'bg-gray-100 text-gray-700',
    '悲伤': 'bg-indigo-100 text-indigo-700',
  };
  return styles[emotion] || 'bg-gray-100 text-gray-600';
}

// 根据标签返回对应的颜色样式
function getTagStyles(tag: string): string {
  const styles: Record<string, string> = {
    '生活': 'bg-orange-100 text-orange-700',
    '北京': 'bg-indigo-100 text-indigo-700',
    '美食': 'bg-pink-100 text-pink-700',
    '天气': 'bg-sky-100 text-sky-700',
    '日常': 'bg-lime-100 text-lime-700',
    '心情': 'bg-rose-100 text-rose-700',
    '旅行': 'bg-cyan-100 text-cyan-700',
    '学习': 'bg-amber-100 text-amber-700',
  };
  return styles[tag] || 'bg-blue-100 text-blue-700';
}

// 节目名称样式
function getProgramStyles(index: number): string {
  const styles = [
    'bg-indigo-100 text-indigo-700',
    'bg-purple-100 text-purple-700',
    'bg-pink-100 text-pink-700',
    'bg-rose-100 text-rose-700',
    'bg-orange-100 text-orange-700',
    'bg-amber-100 text-amber-700',
    'bg-emerald-100 text-emerald-700',
    'bg-cyan-100 text-cyan-700',
    'bg-blue-100 text-blue-700',
    'bg-violet-100 text-violet-700',
  ];
  return styles[index % styles.length];
}

export default function Library() {
  const [clips, setClips] = useState<AudioClip[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedEmotion, setSelectedEmotion] = useState<string>('');
  const [selectedTag, setSelectedTag] = useState<string>('');

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [totalCount, setTotalCount] = useState(0);

  const emotions = ['全部', '开心', '惊喜', '平静', '愤怒', '恐惧', '悲伤'];
  const allTags = ['生活', '北京', '美食', '天气', '日常', '心情', '旅行', '学习'];

  // 加载语弹数据（带分页）
  const loadClips = async (page: number = 1) => {
    setLoading(true);
    try {
      // 先获取总数
      const countResponse = await api.get<{ data: AudioClip[]; total: number }>(`/v1/audio/segments?limit=2000`);
      const allClips = (countResponse?.data || []).filter(clip => clip && typeof clip === 'object');

      // 客户端筛选
      const filtered = allClips.filter(clip => {
        if (!clip || typeof clip !== 'object') return false;
        const searchLower = String(searchTerm || '').toLowerCase();
        const transcription = String(clip.transcription || '');
        const title = String(clip.title || '');
        const matchesSearch = searchLower === '' ||
                             transcription.toLowerCase().includes(searchLower) ||
                             title.toLowerCase().includes(searchLower);
        const matchesEmotion = !selectedEmotion || selectedEmotion === '全部' || clip?.emotion === selectedEmotion;
        const matchesTag = !selectedTag || (clip?.tags || []).includes(selectedTag);
        return matchesSearch && matchesEmotion && matchesTag;
      });

      setTotalCount(filtered.length);

      // 分页
      const start = (page - 1) * pageSize;
      const end = start + pageSize;
      const pagedClips = filtered.slice(start, end);

      setClips(pagedClips);
      setCurrentPage(page);
    } catch (error) {
      console.error('Error loading clips:', error);
      setClips([]);
      setTotalCount(0);
    }
    setLoading(false);
  };

  // 获取所有语弹用于筛选计数
  const [allClips, setAllClips] = useState<AudioClip[]>([]);

  const loadAllClips = async () => {
    try {
      const response = await api.get<{ data: AudioClip[]; total: number }>(`/v1/audio/segments?limit=2000`);
      const validClips = (response?.data || []).filter(clip => clip && typeof clip === 'object');
      setAllClips(validClips);
    } catch (error) {
      console.error('Error loading all clips:', error);
    }
  };

  useEffect(() => {
    loadAllClips();
  }, []);

  useEffect(() => {
    loadClips(1);
  }, [searchTerm, selectedEmotion, selectedTag, pageSize]);

  const deleteClip = async (id: string) => {
    if (!confirm('确定要删除这条语弹吗？')) return;
    try {
      await api.delete(`/v1/audio/favorite/${id}`);
      loadClips(currentPage);
    } catch (error) {
      console.error('Error deleting clip:', error);
    }
  };

  // 计算总页数
  const totalPages = Math.ceil(totalCount / pageSize);

  // 获取节目列表（用于颜色映射）
  const programList = useMemo(() => {
    const programs = [...new Set(allClips.map(clip => clip?.source_title || '未分类节目'))];
    return programs;
  }, [allClips]);

  // 生成页码数组
  const pageNumbers = useMemo(() => {
    const pages: (number | string)[] = [];
    const maxVisible = 5;

    if (totalPages <= maxVisible + 2) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      if (currentPage <= 3) {
        for (let i = 1; i <= 4; i++) pages.push(i);
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
      } else {
        pages.push(1);
        pages.push('...');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i);
        pages.push('...');
        pages.push(totalPages);
      }
    }
    return pages;
  }, [currentPage, totalPages]);

  return (
    <div className="min-h-full bg-gradient-to-br from-purple-50 via-white to-blue-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">精选语弹库</h1>
          <p className="text-gray-600">管理和浏览你的所有音频片段</p>
        </div>

        {/* 筛选栏 */}
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

              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
              >
                <option value={12}>12条/页</option>
                <option value={24}>24条/页</option>
                <option value={48}>48条/页</option>
                <option value={96}>96条/页</option>
              </select>
            </div>
          </div>
        </div>

        {/* 语弹列表 */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
            <p className="text-gray-600 mt-4">加载中...</p>
          </div>
        ) : clips.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
            <Filter className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-800 mb-2">
              {totalCount === 0 ? '还没有语弹片段' : '没有找到匹配的语弹'}
            </h3>
            <p className="text-gray-600">
              {totalCount === 0
                ? '前往"音频工坊"上传并裁切你的第一个音频文件'
                : '尝试调整搜索条件或筛选器'}
            </p>
          </div>
        ) : (
          <>
            {/* 语弹网格 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {clips.map((clip, idx) => (
                <div
                  key={clip?.id || idx}
                  className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow p-4 flex flex-col"
                >
                  {/* 节目标签 */}
                  <div className="flex items-center gap-2 mb-3">
                    <Folder className="w-3.5 h-3.5 text-gray-400" />
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getProgramStyles(programList.indexOf(clip?.source_title || '未分类节目'))}`}>
                      {clip?.source_title || '未分类节目'}
                    </span>
                  </div>

                  {/* 转录文本 */}
                  <p className="text-gray-700 text-sm mb-3 leading-relaxed flex-grow">
                    {cleanTranscription(clip.transcription || '')}
                  </p>

                  {/* 标签区域 */}
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getEmotionStyles(clip?.emotion || '平静')}`}>
                      {clip?.emotion || '平静'}
                    </span>
                    {(clip?.tags || []).slice(0, 2).map((tag, index) => (
                      <span
                        key={index}
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${getTagStyles(tag)}`}
                      >
                        <Tag className="w-3 h-3 mr-0.5" />
                        {tag}
                      </span>
                    ))}
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                      <Clock className="w-3 h-3 mr-0.5" />
                      {clip?.duration || 0}秒
                    </span>
                  </div>

                  {/* 播放器 - 不包含分享按钮 */}
                  <AudioPlayer
                    audioUrl={clip.audio_url || ''}
                    title={clip.title || '语弹片段'}
                    duration={clip.duration || 0}
                  />

                  {/* 操作按钮栏：分享和删除 */}
                  <div className="mt-3 flex items-center gap-2">
                    {/* 分享按钮 */}
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(`分享语弹：${clip.transcription || ''}`);
                        alert('分享链接已复制到剪贴板');
                      }}
                      className="flex-1 flex items-center justify-center gap-1 bg-blue-50 hover:bg-blue-100 text-blue-600 py-2 rounded-lg transition-colors text-sm border border-blue-200"
                      title="分享"
                    >
                      <Share2 className="w-4 h-4" />
                      分享
                    </button>

                    {/* 删除按钮 */}
                    <button
                      onClick={() => clip?.id && deleteClip(clip.id)}
                      className="flex-1 flex items-center justify-center gap-1 text-red-500 hover:text-red-700 py-2 hover:bg-red-50 rounded-lg transition-colors text-sm border border-red-200 hover:border-red-300"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* 分页控制 */}
            {totalPages > 1 && (
              <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4 bg-white rounded-xl shadow p-4">
                <div className="text-sm text-gray-600">
                  共 <span className="font-medium text-gray-800">{totalCount}</span> 条语弹
                  {totalCount > 0 && (
                    <span className="ml-2">
                      第 <span className="font-medium text-gray-800">{currentPage}</span> / {totalPages} 页
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {/* 上一页 */}
                  <button
                    onClick={() => loadClips(currentPage - 1)}
                    disabled={currentPage === 1}
                    className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      currentPage === 1
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    上一页
                  </button>

                  {/* 页码 */}
                  <div className="flex items-center gap-1">
                    {pageNumbers.map((page, index) => (
                      page === '...' ? (
                        <span key={`ellipsis-${index}`} className="px-2 text-gray-400">...</span>
                      ) : (
                        <button
                          key={page}
                          onClick={() => loadClips(page as number)}
                          className={`min-w-[36px] px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                            currentPage === page
                              ? 'bg-blue-500 text-white'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {page}
                        </button>
                      )
                    ))}
                  </div>

                  {/* 下一页 */}
                  <button
                    onClick={() => loadClips(currentPage + 1)}
                    disabled={currentPage === totalPages}
                    className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      currentPage === totalPages
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    下一页
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
// Updated at 2026年04月17日  5:50:22
