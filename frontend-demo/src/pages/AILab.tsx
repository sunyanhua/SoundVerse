import { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, Lightbulb, RefreshCw, Heart } from 'lucide-react';
import { api, Conversation } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import AudioPlayer from '../components/AudioPlayer';

const mockResponses = [
  {
    text: '刚才在广播里听到一段特别有意思的内容，让我想起了小时候的一些回忆。',
    audioUrl: 'https://example.com/response1.mp3',
    duration: 8,
  },
  {
    text: '北京的秋天真是太美了，到处都是金黄色的银杏叶，特别适合散步。',
    audioUrl: 'https://example.com/response2.mp3',
    duration: 9,
  },
  {
    text: '今天尝试了一家新开的川菜馆，麻辣鲜香，简直是味蕾的盛宴！',
    audioUrl: 'https://example.com/response3.mp3',
    duration: 7,
  },
  {
    text: '最近工作有点忙，但每天坚持健身让我感觉精力充沛。',
    audioUrl: 'https://example.com/response4.mp3',
    duration: 6,
  },
  {
    text: '和朋友们聊天的时候，总能发现一些新的有趣观点。',
    audioUrl: 'https://example.com/response5.mp3',
    duration: 7,
  },
];

const fallbackPrompts = [
  '分享一段你今天的见闻',
  '描述一下你最近的心情',
  '推荐一个你喜欢的地方',
  '讲讲你的一个小习惯',
  '说说你最喜欢的美食',
  '聊聊你的周末计划',
  '分享一个难忘的瞬间',
  '说说你正在学习的东西',
  '描述你理想的一天',
  '推荐一本好书或电影',
  '讲讲你的旅行经历',
  '分享你的健身心得',
];

interface PresetPrompt {
  id: string;
  query_text: string;
  category?: string;
}

interface PromptSuggestion {
  id: string;
  text: string;
}

export default function AILab() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [promptSuggestions, setPromptSuggestions] = useState<PromptSuggestion[]>([]);
  const [likedMessages, setLikedMessages] = useState<Set<string>>(new Set());
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const shuffleLocalPrompts = () => {
    const shuffled = [...fallbackPrompts].sort(() => 0.5 - Math.random());
    setPromptSuggestions(shuffled.slice(0, 6).map((text, index) => ({
      id: `local-${index}`,
      text,
    })));
  };

  const fetchRandomPrompts = async () => {
    try {
      const prompts = await api.get<PresetPrompt[]>('/v1/chat/preset-prompts/random?count=6');
      if (prompts && prompts.length > 0) {
        setPromptSuggestions(prompts.map(p => ({ id: p.id, text: p.query_text })));
      } else {
        shuffleLocalPrompts();
      }
    } catch {
      shuffleLocalPrompts();
    }
  };

  useEffect(() => {
    fetchRandomPrompts();

    // 检查是否有从提示词管理页面传来的待加载提示词
    const pendingPrompt = sessionStorage.getItem('ai_lab_pending_prompt');
    if (pendingPrompt) {
      setInputText(pendingPrompt);
      sessionStorage.removeItem('ai_lab_pending_prompt');
      // 可选：自动聚焦输入框
      setTimeout(() => {
        const inputElement = document.querySelector('input[type="text"]') as HTMLInputElement;
        inputElement?.focus();
      }, 100);
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [conversations]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (message: string) => {
    if (!message.trim() || !user) return;

    const userMsg: Conversation = {
      id: `local-${Date.now()}`,
      user_id: user.id,
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    };

    setConversations(prev => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      console.log('Sending message:', message);
      const response = await api.post<{
        message: {
          id: string;
          content: string;
          audio_url?: string;
          similarity_score?: number;
          audio_segment_preview?: {
            id?: string;
            title?: string;
            duration?: number;
            source_title?: string;
          };
        };
        session_id: string;
      }>('/v1/chat/message', {
        content: message,
        session_id: sessionId,
      });

      console.log('API response:', response);
      console.log('Message data:', response.message);
      console.log('Audio URL:', response.message?.audio_url);
      console.log('Similarity:', response.message?.similarity_score);
      console.log('Preview:', response.message?.audio_segment_preview);

      if (response.session_id && !sessionId) {
        setSessionId(response.session_id);
      }

      const assistantMsg: Conversation = {
        id: response.message.id || `local-${Date.now()}-resp`,
        user_id: 'assistant',
        role: 'assistant',
        content: response.message.content,
        audio_url: response.message.audio_url,
        similarity_score: response.message.similarity_score,
        audio_segment_preview: response.message.audio_segment_preview,
        created_at: new Date().toISOString(),
      };

      setConversations(prev => [...prev, assistantMsg]);
    } catch (error) {
      console.error('API error:', error);
      await new Promise(resolve => setTimeout(resolve, 1500));
      const randomResponse = mockResponses[Math.floor(Math.random() * mockResponses.length)];
      const assistantMsg: Conversation = {
        id: `local-${Date.now()}-resp`,
        user_id: 'assistant',
        role: 'assistant',
        content: randomResponse.text,
        created_at: new Date().toISOString(),
      };
      setConversations(prev => [...prev, assistantMsg]);
    }

    setLoading(false);
  };

  const handleLike = async (messageId: string) => {
    const isLiked = likedMessages.has(messageId);
    const newLiked = new Set(likedMessages);

    if (isLiked) {
      newLiked.delete(messageId);
    } else {
      newLiked.add(messageId);
    }
    setLikedMessages(newLiked);

    try {
      await api.put(`/v1/chat/messages/${messageId}/like`, {
        like: !isLiked,
        save_as_preset: !isLiked,
      });
      if (!isLiked) {
        fetchRandomPrompts();
      }
    } catch {
      // 静默失败，本地状态已更新
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  const handleSuggestionClick = (suggestion: PromptSuggestion) => {
    setInputText(suggestion.text);
    // 如果是服务器端的提示词（非本地fallback），更新使用次数
    if (!suggestion.id.startsWith('local-')) {
      api.post(`/v1/chat/preset-prompts/${suggestion.id}/use`, {}).catch(() => {
        // 静默失败，不影响用户体验
      });
    }
  };

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="bg-white shadow-md border-b border-gray-200 p-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold text-gray-800 mb-1 flex items-center">
            <Sparkles className="w-6 h-6 text-blue-500 mr-2" />
            AI 对话实验室
          </h1>
          <p className="text-gray-600 text-sm">与 AI 互动，获取带有真实音频的回复体验</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {conversations.length === 0 ? (
            <div className="text-center py-12">
              <div className="bg-gradient-to-br from-blue-100 to-purple-100 rounded-full w-20 h-20 flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-10 h-10 text-blue-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-800 mb-2">开始你的 AI 对话体验</h3>
              <p className="text-gray-600 mb-6">输入任何话题，AI 会用带音频的方式回复你</p>

              <div className="max-w-2xl mx-auto">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-medium text-gray-700">推荐话题</h4>
                  <button
                    onClick={fetchRandomPrompts}
                    className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" />
                    换一换
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {promptSuggestions.map((suggestion) => (
                    <button
                      key={suggestion.id}
                      onClick={() => handleSuggestionClick(suggestion)}
                      className="flex items-start p-4 bg-white rounded-xl shadow-md hover:shadow-lg transition-all text-left border border-gray-200 hover:border-blue-300"
                    >
                      <Lightbulb className="w-5 h-5 text-yellow-500 mr-3 flex-shrink-0 mt-0.5" />
                      <span className="text-gray-700">{suggestion.text}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`flex ${conv.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-2xl ${
                    conv.role === 'user'
                      ? 'bg-blue-500 text-white rounded-2xl rounded-br-md'
                      : 'bg-white border border-gray-200 rounded-2xl rounded-bl-md shadow-md'
                  } p-4`}
                >
                  {conv.role === 'assistant' ? (
                    <div>
                      <p className="text-gray-800 mb-3">{conv.content}</p>

                      {/* 匹配信息卡片 - 始终显示 */}
                      <div className="bg-gray-50 rounded-lg p-3 mb-3 border border-gray-200">
                        {/* 调试信息 */}
                        {console.log('Rendering assistant message:', { audio_url: conv.audio_url, similarity: conv.similarity_score, preview: conv.audio_segment_preview })}

                        {/* 音频播放器 */}
                        {conv.audio_url ? (
                          <AudioPlayer
                            audioUrl={conv.audio_url}
                            title={conv.audio_segment_preview?.title || "广播片段"}
                            duration={conv.audio_segment_preview?.duration}
                          />
                        ) : (
                          <p className="text-sm text-orange-500 italic mb-2">音频暂不可用</p>
                        )}

                        {/* 匹配度和来源信息 - 强制显示 */}
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                          <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded font-medium">
                            匹配度: {conv.similarity_score ? (conv.similarity_score * 100).toFixed(1) : '0.0'}%
                          </span>
                          <span className="bg-gray-100 text-gray-700 px-2 py-1 rounded font-medium">
                            来源: {conv.audio_segment_preview?.source_title || conv.source_title || '未知'}
                          </span>
                          <span className="text-gray-400 text-xs">
                            ID: {(conv.audio_segment_preview?.id || conv.audio_segment_id || 'unknown').slice(0, 8)}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleLike(conv.id)}
                        className={`mt-2 flex items-center gap-1 text-sm transition-colors ${
                          likedMessages.has(conv.id)
                            ? 'text-red-500'
                            : 'text-gray-400 hover:text-red-400'
                        }`}
                      >
                        <Heart className={`w-4 h-4 ${likedMessages.has(conv.id) ? 'fill-current' : ''}`} />
                        {likedMessages.has(conv.id) ? '已收藏' : '收藏'}
                      </button>
                    </div>
                  ) : (
                    <p>{conv.content}</p>
                  )}
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-md shadow-md p-4">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="bg-white border-t border-gray-200 p-6 shadow-lg">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="输入你想说的话..."
              disabled={loading}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={loading || !inputText.trim()}
              className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white px-6 py-3 rounded-xl transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>

          {conversations.length > 0 && (
            <div className="mt-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs text-gray-500">快速话题</span>
                <button
                  onClick={fetchRandomPrompts}
                  disabled={loading}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className="w-3 h-3" />
                  换一换
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {promptSuggestions.slice(0, 4).map((suggestion) => (
                  <button
                    key={suggestion.id}
                    onClick={() => handleSuggestionClick(suggestion)}
                    disabled={loading}
                    className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {suggestion.text}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
