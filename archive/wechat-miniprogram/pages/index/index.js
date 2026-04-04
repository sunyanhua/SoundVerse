// 首页逻辑
const { resolveAudioUrl, getBaseUrl } = require('../../config');
Page({
    /**
     * 页面的初始数据
     */
    data: {
        isLoading: true,
        recommendedAudios: [],
        userInfo: null,
        showAudioPreview: false,
        previewAudio: {
            title: '',
            audioUrl: '',
            duration: 0,
            tags: [],
        },
    },
    /**
     * 生命周期函数--监听页面加载
     */
    onLoad() {
        this.loadRecommendedAudios();
        this.checkLoginStatus();
    },
    /**
     * 生命周期函数--监听页面显示
     */
    onShow() {
        // 页面显示时更新用户信息
        const userInfo = wx.getStorageSync('userInfo');
        if (userInfo) {
            this.setData({ userInfo });
        }
    },
    /**
     * 生命周期函数--监听页面初次渲染完成
     */
    onReady() {
    },
    /**
     * 生命周期函数--监听页面隐藏
     */
    onHide() {
    },
    /**
     * 生命周期函数--监听页面卸载
     */
    onUnload() {
    },
    /**
     * 页面相关事件处理函数--监听用户下拉动作
     */
    onPullDownRefresh() {
        this.loadRecommendedAudios(() => {
            wx.stopPullDownRefresh();
        });
    },
    /**
     * 页面上拉触底事件的处理函数
     */
    onReachBottom() {
        // 加载更多
    },
    /**
     * 用户点击右上角分享
     */
    onShareAppMessage() {
        return {
            title: '听听·原声态 - AI智能音频社交平台',
            path: '/pages/index/index',
            imageUrl: 'https://picsum.photos/400/300?random=3',
        };
    },
    /**
     * 加载推荐音频
     */
    async loadRecommendedAudios(callback) {
        this.setData({ isLoading: true });
        try {
            // 调用真实API获取推荐音频
            const response = await new Promise((resolve, reject) => {
                wx.request({
                    url: getBaseUrl() + '/api/v1/audio/recommended',
                    method: 'GET',
                    data: {
                        limit: 10,
                    },
                    header: {
                        'Content-Type': 'application/json',
                    },
                    success: (res) => {
                        if (res.statusCode === 200) {
                            resolve(res.data);
                        }
                        else {
                            reject(new Error(`API请求失败: ${res.statusCode}`));
                        }
                    },
                    fail: (err) => {
                        reject(err);
                    },
                });
            });
            // 映射API响应到前端格式
            const audios = response.map((item) => ({
                id: item.id,
                title: item.transcription ?
                    (item.transcription.length > 20 ? item.transcription.substring(0, 20) + '...' : item.transcription)
                    : '音频片段',
                duration: Math.round(item.duration || 0),
                tags: item.tags && item.tags.length > 0 ? item.tags.slice(0, 3) : ['音频'],
                coverUrl: 'https://picsum.photos/200/200?random=' + Math.floor(Math.random() * 100),
                audioUrl: resolveAudioUrl(item.oss_url || ''),
            }));
            this.setData({
                recommendedAudios: audios,
                isLoading: false,
            });
            if (callback)
                callback();
        }
        catch (error) {
            console.error('加载推荐音频失败:', error);
            wx.showToast({
                title: '加载失败',
                icon: 'none',
            });
            // 失败时使用模拟数据作为降级方案
            const mockAudios = [
                {
                    id: '1',
                    title: '早间新闻精选',
                    duration: 45,
                    tags: ['新闻', '资讯', '早间'],
                    coverUrl: 'https://picsum.photos/200/200?random=4',
                    audioUrl: 'https://example.com/audio1.mp3',
                },
                {
                    id: '2',
                    title: '经典音乐欣赏',
                    duration: 120,
                    tags: ['音乐', '经典', '放松'],
                    coverUrl: 'https://picsum.photos/200/200?random=5',
                    audioUrl: 'https://example.com/audio2.mp3',
                },
                {
                    id: '3',
                    title: '英语学习片段',
                    duration: 60,
                    tags: ['教育', '英语', '学习'],
                    coverUrl: 'https://picsum.photos/200/200?random=6',
                    audioUrl: 'https://example.com/audio3.mp3',
                },
            ];
            this.setData({
                recommendedAudios: mockAudios,
                isLoading: false,
            });
            if (callback)
                callback();
        }
    },
    /**
     * 检查登录状态
     */
    checkLoginStatus() {
        const token = wx.getStorageSync('token');
        const userInfo = wx.getStorageSync('userInfo');
        if (!token || !userInfo) {
            // 未登录，可以跳转到登录页面或显示登录提示
            // 这里暂时不处理
        }
        else {
            this.setData({ userInfo });
        }
    },
    /**
     * 跳转到聊天页面
     */
    goToChat() {
        wx.switchTab({
            url: '/pages/chat/chat',
        });
    },
    /**
     * 跳转到音频生成页面
     */
    goToGenerate() {
        wx.switchTab({
            url: '/pages/generate/generate',
        });
    },
    /**
     * 跳转到上传页面
     */
    goToUpload() {
        wx.navigateTo({
            url: '/pages/upload/upload',
        });
    },
    /**
     * 跳转到个人中心
     */
    goToProfile() {
        wx.switchTab({
            url: '/pages/profile/profile',
        });
    },
    /**
     * 查看更多推荐
     */
    viewMoreRecommended() {
        wx.navigateTo({
            url: '/pages/audio-list/audio-list?type=recommended',
        });
    },
    /**
     * 播放音频 - 打开预览弹窗
     */
    playAudio(e) {
        const audio = e.currentTarget.dataset.audio;
        this.setData({
            previewAudio: {
                title: audio.title,
                audioUrl: audio.audioUrl,
                duration: audio.duration || 0,
                tags: audio.tags || [],
            },
            showAudioPreview: true,
        });
    },
    /**
     * 关闭音频预览弹窗
     */
    closeAudioPreview() {
        this.setData({
            showAudioPreview: false,
        });
    },
    /**
     * 音频收藏事件处理
     */
    onAudioFavorite(e) {
        const { isFavorite } = e.detail;
        wx.showToast({
            title: isFavorite ? '已收藏' : '取消收藏',
            icon: 'success',
        });
    },
    /**
     * 音频分享事件处理
     */
    onAudioShare() {
        wx.showToast({
            title: '分享功能开发中',
            icon: 'none',
        });
    },
    /**
     * 音频下载事件处理
     */
    onAudioDownload() {
        wx.showToast({
            title: '下载功能开发中',
            icon: 'none',
        });
    },
    /**
     * 音频播放结束事件处理
     */
    onAudioEnded() {
        console.log('音频播放结束');
    },
    /**
     * 音频播放错误事件处理
     */
    onAudioError(e) {
        console.error('音频播放错误:', e.detail);
        wx.showToast({
            title: '播放失败，请重试',
            icon: 'none',
        });
    },
    /**
     * 登录/注册
     */
    async login() {
        try {
            // 微信登录
            const { code } = await wx.login();
            // 调用后端登录API
            // 这里省略具体实现
            wx.showToast({
                title: '登录成功',
                icon: 'success',
            });
        }
        catch (error) {
            console.error('登录失败:', error);
            wx.showToast({
                title: '登录失败',
                icon: 'none',
            });
        }
    },
});
