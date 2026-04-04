import { useState, useEffect, useRef } from 'react';
import { Send, Sparkles, Lightbulb, RefreshCw } from 'lucide-react';
import { supabase, Conversation } from '../lib/supabase';
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

const allPromptSuggestions = [
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

export default function AILab() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [promptSuggestions, setPromptSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const shufflePrompts = () => {
    const shuffled = [...allPromptSuggestions].sort(() => 0.5 - Math.random());
    setPromptSuggestions(shuffled.slice(0, 6));
  };

  useEffect(() => {
    shufflePrompts();
  }, []);

  useEffect(() => {
    loadConversations();
  }, [user]);

  useEffect(() => {
    scrollToBottom();
  }, [conversations]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadConversations = async () => {
    if (!user) return;

    const { data, error } = await supabase
      .from('conversations')
      .select('*')
      .eq('user_id', user.id)
      .order('created_at', { ascending: true });

    if (error) {
      console.error('Error loading conversations:', error);
    } else {
      setConversations(data || []);
    }
  };

  const sendMessage = async (message: string) => {
    if (!message.trim() || !user) return;

    const { data: userData, error: userError } = await supabase.from('conversations').insert({
      user_id: user.id,
      role: 'user',
      content: message,
    }).select();

    if (userError) {
      console.error('Error saving user message:', userError);
      return;
    }

    if (userData) {
      setConversations(prev => [...prev, userData[0]]);
    }

    setInputText('');
    setLoading(true);

    await new Promise(resolve => setTimeout(resolve, 1500));

    const randomResponse = mockResponses[Math.floor(Math.random() * mockResponses.length)];

    const { data: assistantData, error: assistantError } = await supabase.from('conversations').insert({
      user_id: user.id,
      role: 'assistant',
      content: randomResponse.text,
    }).select();

    if (assistantError) {
      console.error('Error saving assistant message:', assistantError);
    } else if (assistantData) {
      setConversations(prev => [...prev, assistantData[0]]);
    }

    setLoading(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(inputText);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputText(suggestion);
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
                    onClick={shufflePrompts}
                    className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" />
                    换一换
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {promptSuggestions.map((suggestion, index) => (
                    <button
                      key={index}
                      onClick={() => handleSuggestionClick(suggestion)}
                      className="flex items-start p-4 bg-white rounded-xl shadow-md hover:shadow-lg transition-all text-left border border-gray-200 hover:border-blue-300"
                    >
                      <Lightbulb className="w-5 h-5 text-yellow-500 mr-3 flex-shrink-0 mt-0.5" />
                      <span className="text-gray-700">{suggestion}</span>
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
                      <AudioPlayer
                        audioUrl={mockResponses[Math.floor(Math.random() * mockResponses.length)].audioUrl}
                        title="AI 语音回复"
                        duration={mockResponses[Math.floor(Math.random() * mockResponses.length)].duration}
                      />
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
                  onClick={shufflePrompts}
                  disabled={loading}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className="w-3 h-3" />
                  换一换
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {promptSuggestions.slice(0, 4).map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => handleSuggestionClick(suggestion)}
                    disabled={loading}
                    className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {suggestion}
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
