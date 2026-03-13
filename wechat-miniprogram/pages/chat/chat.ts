// 聊天页面逻辑
import { post } from '../../services/api';
import type { ChatResponse, ChatMessage } from '../../types/api';

// 页面数据接口
interface PageData {
  // 消息列表
  messages: ChatMessage[];
  // 输入值
  inputValue: string;
  // 加载状态
  isLoading: boolean;
  // 发送状态
  isSending: boolean;
  // 加载更多状态
  isLoadingMore: boolean;
  // 滚动到消息ID
  scrollToId: string;
  // 自动聚焦输入框
  autoFocus: boolean;
  // 快捷问题
  quickQuestions: string[];
  // 当前播放的音频ID
  currentAudioId: string | null;
  // 音频播放进度
  audioProgress: number;
  // 音频播放器实例
  audioContext: WechatMiniprogram.InnerAudioContext | null;
  // 会话ID
  sessionId: string | null;
}

// 页面实例
Page({
  /**
   * 页面的初始数据
   */
  data: {
    messages: [],
    inputValue: '',
    isLoading: false,
    isSending: false,
    isLoadingMore: false,
    scrollToId: '',
    autoFocus: false,
    quickQuestions: [
      '现在几点了？',
      '北京时间是多少？',
      '中央人民广播电台',
      '有什么新闻广播吗？',
      '请报时',
      '天气预报',
      '体育新闻',
      '今天有什么新闻？',
      '欢迎收听新闻广播',
      '国家领导人会议',
      '中国女排',
      '天气预报今天怎么样？'
    ],
    currentAudioId: null,
    audioProgress: 0,
    audioContext: null,
    sessionId: null,
  } as PageData,

  /**
   * 生命周期函数--监听页面加载
   */
  onLoad() {
    // 初始化音频播放器
    this.initAudioPlayer();
    // 加载聊天历史（如果有）
    this.loadChatHistory();
  },

  /**
   * 生命周期函数--监听页面显示
   */
  onShow() {
    // 页面显示时自动聚焦输入框
    this.setData({
      autoFocus: true,
    });
  },

  /**
   * 生命周期函数--监听页面隐藏
   */
  onHide() {
    // 页面隐藏时停止音频播放
    this.stopAudio();
  },

  /**
   * 生命周期函数--监听页面卸载
   */
  onUnload() {
    // 页面卸载时销毁音频播放器
    this.destroyAudioPlayer();
  },

  /**
   * 页面相关事件处理函数--监听用户下拉动作
   */
  onPullDownRefresh() {
    // 下拉刷新聊天记录
    this.loadChatHistory(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 页面上拉触底事件的处理函数
   */
  onReachBottom() {
    // 加载更多历史消息
    this.loadMoreMessages();
  },

  /**
   * 用户点击右上角分享
   */
  onShareAppMessage() {
    return {
      title: '听听·原声态 - AI智能音频聊天',
      path: '/pages/chat/chat',
      imageUrl: 'https://picsum.photos/400/300?random=7',
    };
  },

  /**
   * 初始化音频播放器
   */
  initAudioPlayer() {
    const audioContext = wx.createInnerAudioContext();

    // 设置音频播放器配置
    audioContext.obeyMuteSwitch = false; // 不跟随静音开关

    // 监听音频事件
    audioContext.onPlay(() => {
      console.log('音频开始播放');
    });

    audioContext.onPause(() => {
      console.log('音频暂停');
    });

    audioContext.onStop(() => {
      console.log('音频停止');
      this.setData({
        currentAudioId: null,
        audioProgress: 0,
      });
    });

    audioContext.onEnded(() => {
      console.log('音频播放结束');
      this.setData({
        currentAudioId: null,
        audioProgress: 0,
      });
    });

    audioContext.onError((err) => {
      console.error('音频播放错误:', err);
      wx.showToast({
        title: '音频播放失败',
        icon: 'none',
      });
      this.setData({
        currentAudioId: null,
        audioProgress: 0,
      });
    });

    audioContext.onTimeUpdate(() => {
      if (audioContext.duration > 0) {
        const progress = (audioContext.currentTime / audioContext.duration) * 100;
        this.setData({
          audioProgress: Math.floor(progress),
        });
      }
    });

    this.setData({
      audioContext,
    });
  },

  /**
   * 销毁音频播放器
   */
  destroyAudioPlayer() {
    const { audioContext } = this.data;
    if (audioContext) {
      audioContext.stop();
      audioContext.destroy();
      this.setData({
        audioContext: null,
        currentAudioId: null,
        audioProgress: 0,
      });
    }
  },

  /**
   * 加载聊天历史
   */
  async loadChatHistory(callback?: () => void) {
    // 暂时从本地存储加载消息
    const savedMessages = wx.getStorageSync('chat_messages') || [];
    if (savedMessages.length > 0) {
      this.setData({
        messages: savedMessages,
      });
    }

    // 如果有会话ID，可以从服务器加载历史
    // TODO: 实现服务器端历史加载

    if (callback) callback();
  },

  /**
   * 加载更多消息
   */
  loadMoreMessages() {
    // TODO: 实现加载更多历史消息
    console.log('加载更多消息');
  },

  /**
   * 输入框内容变化
   */
  onInput(e: any) {
    this.setData({
      inputValue: e.detail.value,
    });
  },

  /**
   * 发送消息
   */
  async sendMessage() {
    const { inputValue, isSending, sessionId } = this.data;
    const message = inputValue.trim();

    if (!message || isSending) {
      return;
    }

    // 清空输入框
    this.setData({
      inputValue: '',
      isSending: true,
    });

    // 添加用户消息到列表
    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      session_id: sessionId || '',
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    this.addMessage(userMessage);

    try {
      // 发送到后端API
      const response = await post<ChatResponse>('/api/v1/chat/message', {
        content: message,
        session_id: sessionId,
      });

      if (response.success && response.data) {
        const chatResponse = response.data;

        // 保存会话ID（如果是新会话）
        if (chatResponse.session && !sessionId) {
          this.setData({
            sessionId: chatResponse.session.id,
          });
        }

        // 添加助手消息到列表
        const assistantMessage = chatResponse.message;
        this.addMessage(assistantMessage);

        // 保存消息到本地存储
        this.saveMessagesToStorage();

        // 更新快捷问题为API返回的建议
        if (chatResponse.suggestions && chatResponse.suggestions.length > 0) {
          this.setData({
            quickQuestions: chatResponse.suggestions
          });
        }
      } else {
        // 显示错误
        wx.showToast({
          title: response.message || '发送失败',
          icon: 'none',
        });

        // 添加错误消息
        const errorMessage: ChatMessage = {
          id: `error_${Date.now()}`,
          session_id: sessionId || '',
          role: 'assistant',
          content: '抱歉，暂时无法处理您的请求，请稍后重试。',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        this.addMessage(errorMessage);
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      wx.showToast({
        title: '网络连接失败',
        icon: 'none',
      });

      // 添加错误消息
      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        session_id: sessionId || '',
        role: 'assistant',
        content: '网络连接失败，请检查网络设置。',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      this.addMessage(errorMessage);
    } finally {
      this.setData({
        isSending: false,
      });
    }
  },

  /**
   * 发送快捷问题
   */
  sendQuickQuestion(e: any) {
    const question = e.currentTarget.dataset.question;
    if (question) {
      this.setData({
        inputValue: question,
      }, () => {
        // 延迟发送，确保inputValue已更新
        setTimeout(() => {
          this.sendMessage();
        }, 100);
      });
    }
  },

  /**
   * 添加消息到列表
   */
  addMessage(message: ChatMessage) {
    const { messages } = this.data;
    const updatedMessages = [...messages, message];

    this.setData({
      messages: updatedMessages,
    }, () => {
      // 滚动到最新消息
      this.scrollToMessage(message.id);
    });
  },

  /**
   * 滚动到指定消息
   */
  scrollToMessage(messageId: string) {
    this.setData({
      scrollToId: `msg-${messageId}`,
    });
  },

  /**
   * 播放音频
   */
  playAudio(e: any) {
    const { audioContext, currentAudioId } = this.data;
    const audioUrl = e.currentTarget.dataset.audioUrl;
    const messageId = e.currentTarget.dataset.messageId;

    console.log('playAudio被调用:');
    console.log('音频URL:', audioUrl);
    console.log('消息ID:', messageId);
    console.log('当前播放ID:', currentAudioId);

    if (!audioContext || !audioUrl) {
      console.error('音频播放器未初始化或音频URL为空');
      return;
    }

    // 如果正在播放同一个音频，则暂停
    if (currentAudioId === messageId) {
      console.log('正在播放同一个音频，暂停');
      this.stopAudio();
      return;
    }

    // 停止当前播放的音频
    if (currentAudioId) {
      console.log('停止当前播放的音频:', currentAudioId);
      audioContext.stop();
    }

    // 设置音频源并播放
    console.log('设置音频源:', audioUrl);
    audioContext.src = audioUrl;
    console.log('audioContext.src已设置为:', audioContext.src);

    // 微信小程序的play()方法不返回Promise，需要使用try-catch
    try {
      audioContext.play();
      console.log('开始播放音频');
      this.setData({
        currentAudioId: messageId,
        audioProgress: 0,
      });
    } catch (error) {
      console.error('音频播放失败:', error);
      wx.showToast({
        title: '音频播放失败',
        icon: 'none',
      });
    }
  },

  /**
   * 停止音频播放
   */
  stopAudio() {
    const { audioContext } = this.data;
    if (audioContext) {
      audioContext.stop();
      this.setData({
        currentAudioId: null,
        audioProgress: 0,
      });
    }
  },

  /**
   * 格式化时间
   */
  formatTime(isoString: string): string {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);

      if (diffMins < 1) {
        return '刚刚';
      } else if (diffMins < 60) {
        return `${diffMins}分钟前`;
      } else if (diffMins < 1440) {
        return `${Math.floor(diffMins / 60)}小时前`;
      } else {
        return `${Math.floor(diffMins / 1440)}天前`;
      }
    } catch (error) {
      return '';
    }
  },

  /**
   * 保存消息到本地存储
   */
  saveMessagesToStorage() {
    const { messages } = this.data;
    try {
      wx.setStorageSync('chat_messages', messages.slice(-50)); // 只保存最近50条
    } catch (error) {
      console.error('保存消息失败:', error);
    }
  },

  /**
   * 清除聊天记录
   */
  clearChatHistory() {
    wx.showModal({
      title: '清除聊天记录',
      content: '确定要清除所有聊天记录吗？',
      success: (res) => {
        if (res.confirm) {
          this.setData({
            messages: [],
            sessionId: null,
          });
          wx.removeStorageSync('chat_messages');
          wx.showToast({
            title: '已清除',
            icon: 'success',
          });
        }
      },
    });
  },

  /**
   * 复制文本
   */
  copyText(e: any) {
    const text = e.currentTarget.dataset.text;
    if (text) {
      wx.setClipboardData({
        data: text,
        success: () => {
          wx.showToast({
            title: '已复制',
            icon: 'success',
          });
        },
      });
    }
  },
});