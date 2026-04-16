import { useState, useEffect } from 'react';
import { Trash2, RefreshCw, MessageSquare, Tag, ThumbsUp, Calendar, AlertCircle } from 'lucide-react';
import { api } from '../lib/api';

interface PresetPrompt {
  id: string;
  query_text: string;
  category: string | null;
  emotion: string | null;
  tags: string[];
  like_count: number;
  use_count: number;
  review_status: string;
  created_at: string;
  user_nickname?: string;
}

export default function PromptManager() {
  const [prompts, setPrompts] = useState<PresetPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 加载提示词列表
  const loadPrompts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<PresetPrompt[]>('/v1/chat/preset-prompts/my');
      setPrompts(response || []);
    } catch (err) {
      console.error('Error loading prompts:', err);
      setError('加载提示词失败');
    }
    setLoading(false);
  };

  useEffect(() => {
    loadPrompts();
  }, []);

  // 删除提示词
  const deletePrompt = async (id: string) => {
    if (!confirm('确定要删除这条提示词吗？')) return;

    setDeleting(id);
    try {
      await api.delete(`/v1/chat/preset-prompts/${id}`);
      setPrompts(prompts.filter(p => p.id !== id));
    } catch (err) {
      console.error('Error deleting prompt:', err);
      alert('删除失败');
    }
    setDeleting(null);
  };

  // 格式化日期
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // 获取分类颜色
  const getCategoryColor = (category: string | null) => {
    const colors: Record<string, string> = {
      '对话': 'bg-blue-100 text-blue-700',
      '音乐': 'bg-purple-100 text-purple-700',
      '学习': 'bg-green-100 text-green-700',
      '天气': 'bg-sky-100 text-sky-700',
      '美食': 'bg-orange-100 text-orange-700',
      '旅行': 'bg-cyan-100 text-cyan-700',
    };
    return colors[category || ''] || 'bg-gray-100 text-gray-700';
  };

  return (
    <div className="min-h-full bg-gradient-to-br from-purple-50 via-white to-blue-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* 标题栏 */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-800 mb-2">提示词管理</h1>
            <p className="text-gray-600">管理你保存的提示词，删除不再需要的提示词</p>
          </div>
          <button
            onClick={loadPrompts}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white rounded-lg transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* 提示词列表 */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
            <p className="text-gray-600 mt-4">加载中...</p>
          </div>
        ) : prompts.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-xl p-12 text-center">
            <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-800 mb-2">还没有保存的提示词</h3>
            <p className="text-gray-600">
              在 AI 对话实验室中点赞喜欢的回复，可以保存为提示词
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">提示词内容</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">分类</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">统计</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-700">创建时间</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-gray-700">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {prompts.map((prompt) => (
                    <tr key={prompt.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4">
                        <div className="max-w-md">
                          <p className="text-gray-800 text-sm line-clamp-2" title={prompt.query_text}>
                            {prompt.query_text}
                          </p>
                          {prompt.tags && prompt.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-2">
                              {prompt.tags.map((tag, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600"
                                >
                                  <Tag className="w-3 h-3 mr-1" />
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {prompt.category ? (
                          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${getCategoryColor(prompt.category)}`}>
                            {prompt.category}
                          </span>
                        ) : (
                          <span className="text-gray-400 text-sm">未分类</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <span className="flex items-center gap-1" title="点赞数">
                            <ThumbsUp className="w-4 h-4 text-pink-500" />
                            {prompt.like_count}
                          </span>
                          <span className="flex items-center gap-1" title="使用次数">
                            <MessageSquare className="w-4 h-4 text-blue-500" />
                            {prompt.use_count}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="flex items-center gap-1 text-sm text-gray-500">
                          <Calendar className="w-4 h-4" />
                          {formatDate(prompt.created_at)}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => deletePrompt(prompt.id)}
                          disabled={deleting === prompt.id}
                          className="inline-flex items-center gap-1 px-3 py-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors text-sm"
                          title="删除"
                        >
                          {deleting === prompt.id ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 底部统计 */}
            <div className="bg-gray-50 px-6 py-4 border-t border-gray-200">
              <p className="text-sm text-gray-600">
                共 <span className="font-medium text-gray-800">{prompts.length}</span> 条提示词
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
