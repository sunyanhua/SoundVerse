"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// 聊天页面逻辑
const api_1 = require("../../services/api");
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
            '测试一下语音识别',
            '通用模型测试',
            '这是语音识别测试'
        ],
        currentAudioId: null,
        audioProgress: 0,
        audioContext: null,
        sessionId: null,
    },
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
    async loadChatHistory(callback) {
        // 暂时从本地存储加载消息
        const savedMessages = wx.getStorageSync('chat_messages') || [];
        if (savedMessages.length > 0) {
            this.setData({
                messages: savedMessages,
            });
        }
        // 如果有会话ID，可以从服务器加载历史
        // TODO: 实现服务器端历史加载
        if (callback)
            callback();
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
    onInput(e) {
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
        const userMessage = {
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
            const response = await (0, api_1.post)('/api/v1/chat/message', {
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
            }
            else {
                // 显示错误
                wx.showToast({
                    title: response.message || '发送失败',
                    icon: 'none',
                });
                // 添加错误消息
                const errorMessage = {
                    id: `error_${Date.now()}`,
                    session_id: sessionId || '',
                    role: 'assistant',
                    content: '抱歉，暂时无法处理您的请求，请稍后重试。',
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                };
                this.addMessage(errorMessage);
            }
        }
        catch (error) {
            console.error('发送消息失败:', error);
            wx.showToast({
                title: '网络连接失败',
                icon: 'none',
            });
            // 添加错误消息
            const errorMessage = {
                id: `error_${Date.now()}`,
                session_id: sessionId || '',
                role: 'assistant',
                content: '网络连接失败，请检查网络设置。',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            };
            this.addMessage(errorMessage);
        }
        finally {
            this.setData({
                isSending: false,
            });
        }
    },
    /**
     * 发送快捷问题
     */
    sendQuickQuestion(e) {
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
    addMessage(message) {
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
    scrollToMessage(messageId) {
        this.setData({
            scrollToId: `msg-${messageId}`,
        });
    },
    /**
     * 播放音频
     */
    playAudio(e) {
        const { audioContext, currentAudioId } = this.data;
        const audioUrl = e.currentTarget.dataset.audioUrl;
        const messageId = e.currentTarget.dataset.messageId;
        if (!audioContext || !audioUrl) {
            return;
        }
        // 如果正在播放同一个音频，则暂停
        if (currentAudioId === messageId) {
            this.stopAudio();
            return;
        }
        // 停止当前播放的音频
        if (currentAudioId) {
            audioContext.stop();
        }
        // 设置音频源并播放
        audioContext.src = audioUrl;
        audioContext.play().then(() => {
            this.setData({
                currentAudioId: messageId,
                audioProgress: 0,
            });
        }).catch((error) => {
            console.error('音频播放失败:', error);
            wx.showToast({
                title: '音频播放失败',
                icon: 'none',
            });
        });
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
    formatTime(isoString) {
        try {
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now.getTime() - date.getTime();
            const diffMins = Math.floor(diffMs / 60000);
            if (diffMins < 1) {
                return '刚刚';
            }
            else if (diffMins < 60) {
                return `${diffMins}分钟前`;
            }
            else if (diffMins < 1440) {
                return `${Math.floor(diffMins / 60)}小时前`;
            }
            else {
                return `${Math.floor(diffMins / 1440)}天前`;
            }
        }
        catch (error) {
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
        }
        catch (error) {
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
    copyText(e) {
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
