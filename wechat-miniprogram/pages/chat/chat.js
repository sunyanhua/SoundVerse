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
            '今天过得怎么样？',
            '有什么新鲜事分享吗？',
            '最近忙什么呢？',
            '来聊聊天吧',
            '今天天气不错',
            '路上堵不堵？',
            '我有个小经验想分享',
            '说实话，我觉得挺有意思',
            '哎，我跟你说个事',
            '其实吧，这样挺好',
            '周末有什么安排？',
            '推荐一本好书吧'
        ],
        currentAudioId: null,
        isPlaying: false,
        audioProgress: 0,
        audioContext: null,
        sessionId: null,
        autoPlayEnabled: true,
        // 语音录音相关
        isRecording: false,
        recorderManager: null,
        recordTime: 0,
        recordFile: null,
    },
    /**
     * 生命周期函数--监听页面加载
     */
    onLoad() {
        // 初始化音频播放器
        this.initAudioPlayer();
        // 初始化录音管理器
        this.initRecorderManager();
        // 加载聊天历史（如果有）
        this.loadChatHistory();
        // 加载快捷问题（提示语句）
        this.loadQuickQuestions();
        // 加载自动播放设置（默认启用）
        const autoPlayEnabled = wx.getStorageSync('auto_play_enabled');
        if (autoPlayEnabled !== '') {
            this.setData({
                autoPlayEnabled: autoPlayEnabled === true || autoPlayEnabled === 'true',
            });
        }
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
        // 停止录音并清理录音管理器
        const { recorderManager, isRecording } = this.data;
        if (isRecording && recorderManager) {
            recorderManager.stop();
        }
        // 清除计时器
        if (this.recordTimer) {
            clearInterval(this.recordTimer);
            this.recordTimer = null;
        }
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
            this.setData({
                isPlaying: true,
            });
        });
        audioContext.onPause(() => {
            console.log('音频暂停');
            this.setData({
                isPlaying: false,
            });
        });
        audioContext.onStop(() => {
            console.log('音频停止');
            this.setData({
                currentAudioId: null,
                isPlaying: false,
                audioProgress: 0,
            });
        });
        audioContext.onEnded(() => {
            console.log('音频播放结束');
            this.setData({
                currentAudioId: null,
                isPlaying: false,
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
                isPlaying: false,
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
                isPlaying: false,
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
                // 延迟自动播放音频（如果存在音频URL）
                if (assistantMessage.audio_url) {
                    setTimeout(() => {
                        this.autoPlayAudioDirectly(assistantMessage.id, assistantMessage.audio_url);
                    }, 500); // 延迟500毫秒，确保消息已渲染
                }
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
        const { audioContext, currentAudioId, isPlaying } = this.data;
        const audioUrl = e.currentTarget.dataset.audioUrl;
        const messageId = e.currentTarget.dataset.messageId;
        console.log('playAudio被调用:');
        console.log('音频URL:', audioUrl);
        console.log('消息ID:', messageId);
        console.log('当前播放ID:', currentAudioId);
        console.log('当前播放状态:', isPlaying);
        if (!audioContext || !audioUrl) {
            console.error('音频播放器未初始化或音频URL为空');
            return;
        }
        // 情况1：点击同一个音频
        if (currentAudioId === messageId) {
            // 如果正在播放，则暂停
            if (isPlaying) {
                console.log('正在播放同一个音频，暂停');
                try {
                    audioContext.pause();
                    // onPause事件会更新isPlaying状态
                }
                catch (error) {
                    console.error('音频暂停失败:', error);
                    wx.showToast({
                        title: '音频暂停失败',
                        icon: 'none',
                    });
                }
            }
            else {
                // 如果已暂停，则恢复播放
                console.log('恢复播放已暂停的音频');
                try {
                    audioContext.play();
                    // onPlay事件会更新isPlaying状态
                }
                catch (error) {
                    console.error('音频恢复播放失败:', error);
                    wx.showToast({
                        title: '音频播放失败',
                        icon: 'none',
                    });
                }
            }
            return;
        }
        // 情况2：点击不同的音频
        // 停止当前播放的音频（如果有）
        if (currentAudioId) {
            console.log('停止当前播放的音频:', currentAudioId);
            audioContext.stop();
            // onStop事件会更新currentAudioId和isPlaying状态
        }
        // 设置音频源并播放
        console.log('设置音频源:', audioUrl);
        audioContext.src = audioUrl;
        console.log('audioContext.src已设置为:', audioContext.src);
        try {
            audioContext.play();
            console.log('开始播放新音频');
            // 立即更新currentAudioId，播放状态由onPlay事件更新
            this.setData({
                currentAudioId: messageId,
                audioProgress: 0,
            });
        }
        catch (error) {
            console.error('音频播放失败:', error);
            wx.showToast({
                title: '音频播放失败',
                icon: 'none',
            });
            // 播放失败时清除状态
            this.setData({
                currentAudioId: null,
                isPlaying: false,
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
            // onStop事件会更新状态，但为了确保立即更新，这里也设置状态
            this.setData({
                currentAudioId: null,
                isPlaying: false,
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
    /**
     * 自动播放音频（延迟自动播放）- 改进版
     */
    autoPlayAudioDirectly(messageId, audioUrl) {
        const { audioContext, currentAudioId, isPlaying, autoPlayEnabled } = this.data;
        // 检查自动播放是否启用
        if (!autoPlayEnabled) {
            console.log('自动播放已禁用，跳过自动播放');
            return;
        }
        if (!audioContext || !audioUrl) {
            console.error('音频播放器未初始化或音频URL为空');
            return;
        }
        // 如果正在播放同一个音频，则暂停（不应该发生，但为了安全）
        if (currentAudioId === messageId && isPlaying) {
            console.log('正在播放同一个音频，暂停');
            this.stopAudio();
            return;
        }
        // 停止当前播放的音频
        if (currentAudioId && isPlaying) {
            console.log('停止当前播放的音频:', currentAudioId);
            this.stopAudio();
        }
        // 设置音频源
        console.log('设置音频源:', audioUrl);
        audioContext.src = audioUrl;
        // 监听音频加载完成事件
        const onCanplay = () => {
            // 移除事件监听器，避免重复触发
            audioContext.offCanplay(onCanplay);
            console.log('音频加载完成，开始自动播放');
            try {
                audioContext.play();
                console.log('开始自动播放音频');
                // 立即更新currentAudioId，播放状态由onPlay事件更新
                this.setData({
                    currentAudioId: messageId,
                    audioProgress: 0,
                });
            }
            catch (error) {
                console.error('音频自动播放失败:', error);
                wx.showToast({
                    title: '音频播放失败',
                    icon: 'none',
                });
                // 播放失败时清除状态
                this.setData({
                    currentAudioId: null,
                    isPlaying: false,
                });
            }
        };
        // 添加加载完成事件监听器
        audioContext.onCanplay(onCanplay);
        // 设置超时，防止音频加载失败
        setTimeout(() => {
            // 检查是否仍然需要播放（可能用户已手动操作）
            if (audioContext && audioContext.src === audioUrl && !this.data.isPlaying) {
                // 如果5秒后仍未触发onCanplay，尝试直接播放
                audioContext.offCanplay(onCanplay);
                console.log('音频加载超时，尝试直接播放');
                try {
                    audioContext.play();
                    this.setData({
                        currentAudioId: messageId,
                        audioProgress: 0,
                    });
                }
                catch (error) {
                    console.error('音频自动播放失败（超时后）:', error);
                    wx.showToast({
                        title: '音频加载超时',
                        icon: 'none',
                    });
                    this.setData({
                        currentAudioId: null,
                        isPlaying: false,
                    });
                }
            }
        }, 5000); // 5秒超时
    },
    /**
     * 切换自动播放设置
     */
    toggleAutoPlay() {
        const newValue = !this.data.autoPlayEnabled;
        this.setData({
            autoPlayEnabled: newValue,
        });
        // 保存到本地存储
        wx.setStorageSync('auto_play_enabled', newValue);
        wx.showToast({
            title: newValue ? '已启用自动播放' : '已禁用自动播放',
            icon: 'success',
            duration: 1500,
        });
    },
    /**
     * 初始化录音管理器
     */
    initRecorderManager() {
        const recorderManager = wx.getRecorderManager();
        // 监听录音开始事件
        recorderManager.onStart(() => {
            console.log('录音开始');
            this.setData({
                isRecording: true,
                recordTime: 0,
            });
            // 开始计时
            this.recordTimer = setInterval(() => {
                this.setData({
                    recordTime: this.data.recordTime + 1,
                });
            }, 1000);
        });
        // 监听录音停止事件
        recorderManager.onStop((res) => {
            console.log('录音停止', res);
            const { tempFilePath, duration } = res;
            // 清除计时器
            if (this.recordTimer) {
                clearInterval(this.recordTimer);
                this.recordTimer = null;
            }
            this.setData({
                isRecording: false,
                recordTime: 0,
                recordFile: tempFilePath,
            });
            // 录音完成后自动上传识别
            if (tempFilePath) {
                this.uploadVoiceFile(tempFilePath);
            }
        });
        // 监听录音错误事件
        recorderManager.onError((err) => {
            console.error('录音错误:', err);
            this.handleRecordError(err);
        });
        this.setData({
            recorderManager,
        });
    },
    /**
     * 开始录音
     */
    startRecord() {
        const { recorderManager, isRecording } = this.data;
        if (isRecording) {
            return;
        }
        if (!recorderManager) {
            this.initRecorderManager();
        }
        // 检查录音权限
        wx.authorize({
            scope: 'scope.record',
            success: () => {
                // 开始录音
                recorderManager.start({
                    duration: 60000,
                    sampleRate: 16000,
                    numberOfChannels: 1,
                    encodeBitRate: 48000,
                    format: 'mp3',
                    frameSize: 50,
                });
            },
            fail: (err) => {
                console.error('录音权限授权失败:', err);
                wx.showToast({
                    title: '请授权录音权限',
                    icon: 'none',
                });
            },
        });
    },
    /**
     * 停止录音
     */
    stopRecord() {
        const { recorderManager, isRecording } = this.data;
        if (!isRecording || !recorderManager) {
            return;
        }
        recorderManager.stop();
    },
    /**
     * 上传录音文件进行语音识别
     */
    async uploadVoiceFile(tempFilePath) {
        const { isSending, sessionId } = this.data;
        if (isSending) {
            wx.showToast({
                title: '正在处理中，请稍后',
                icon: 'none',
            });
            return;
        }
        this.setData({
            isSending: true,
        });
        wx.showLoading({
            title: '识别中...',
        });
        try {
            // 上传录音文件到后端进行ASR识别
            const response = await wx.uploadFile({
                url: `${getApp().globalData.baseUrl}/api/v1/chat/voice`,
                filePath: tempFilePath,
                name: 'audio',
                formData: {
                    session_id: sessionId || '',
                    format: 'mp3',
                    sample_rate: '16000',
                },
            });
            if (response.statusCode === 200) {
                const result = JSON.parse(response.data);
                if (result.success && result.text) {
                    // 添加用户消息（语音识别出的文本）
                    const userMessage = {
                        id: `user_${Date.now()}`,
                        session_id: sessionId || '',
                        role: 'user',
                        content: result.text,
                        created_at: new Date().toISOString(),
                        updated_at: new Date().toISOString(),
                    };
                    this.addMessage(userMessage);
                    // 如果后端返回了完整的聊天响应，直接使用它
                    if (result.chat_response) {
                        const chatResponse = result.chat_response;
                        // 保存会话ID（如果是新会话）
                        if (chatResponse.session && !sessionId) {
                            this.setData({
                                sessionId: chatResponse.session.id,
                            });
                        }
                        // 添加助手消息到列表
                        const assistantMessage = chatResponse.message;
                        this.addMessage(assistantMessage);
                        // 延迟自动播放音频（如果存在音频URL）
                        if (assistantMessage.audio_url) {
                            setTimeout(() => {
                                this.autoPlayAudioDirectly(assistantMessage.id, assistantMessage.audio_url);
                            }, 500);
                        }
                        // 保存消息到本地存储
                        this.saveMessagesToStorage();
                    }
                    else {
                        // 如果后端没有返回完整响应，将识别文本设置为输入值，由用户决定是否发送
                        this.setData({
                            inputValue: result.text,
                        });
                        wx.showToast({
                            title: '识别成功，请点击发送',
                            icon: 'success',
                        });
                    }
                }
                else {
                    wx.showToast({
                        title: result.message || '识别失败',
                        icon: 'none',
                    });
                }
            }
            else {
                throw new Error(`上传失败: ${response.statusCode}`);
            }
        }
        catch (error) {
            console.error('语音识别失败:', error);
            wx.showToast({
                title: '语音识别失败，请重试',
                icon: 'none',
            });
        }
        finally {
            wx.hideLoading();
            this.setData({
                isSending: false,
                recordFile: null,
            });
        }
    },
    /**
     * 加载快捷问题（提示语句）
     */
    async loadQuickQuestions() {
        try {
            // 从API获取建议
            const response = await (0, api_1.get)('/api/v1/chat/suggestions');
            if (response.success && response.data && response.data.suggestions) {
                const suggestions = response.data.suggestions;
                // 随机选择10-12个提示语句
                const shuffled = suggestions.sort(() => 0.5 - Math.random());
                const selectedQuestions = shuffled.slice(0, Math.min(12, shuffled.length));
                this.setData({
                    quickQuestions: selectedQuestions,
                });
                console.log('加载快捷问题成功:', selectedQuestions.length, '条');
            }
            else {
                console.warn('获取建议失败，使用默认提示语句');
                // 使用默认提示语句，但随机选择
                const defaultQuestions = this.data.quickQuestions;
                const shuffled = defaultQuestions.sort(() => 0.5 - Math.random());
                const selectedQuestions = shuffled.slice(0, Math.min(12, shuffled.length));
                this.setData({
                    quickQuestions: selectedQuestions,
                });
            }
        }
        catch (error) {
            console.error('加载快捷问题失败:', error);
            // 使用默认提示语句，但随机选择
            const defaultQuestions = this.data.quickQuestions;
            const shuffled = defaultQuestions.sort(() => 0.5 - Math.random());
            const selectedQuestions = shuffled.slice(0, Math.min(12, shuffled.length));
            this.setData({
                quickQuestions: selectedQuestions,
            });
        }
    },
    /**
     * 处理录音错误
     */
    handleRecordError(err) {
        console.error('录音错误:', err);
        // 清除计时器
        if (this.recordTimer) {
            clearInterval(this.recordTimer);
            this.recordTimer = null;
        }
        this.setData({
            isRecording: false,
            recordTime: 0,
            recordFile: null,
        });
        wx.showToast({
            title: '录音失败，请重试',
            icon: 'none',
        });
    },
});
