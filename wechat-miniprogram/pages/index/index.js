// 首页逻辑
Page({
    /**
     * 页面的初始数据
     */
    data: {
        isLoading: true,
        recommendedAudios: [],
        userInfo: null,
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
            // 这里应该调用API获取推荐音频
            // 暂时使用模拟数据
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
        catch (error) {
            console.error('加载推荐音频失败:', error);
            wx.showToast({
                title: '加载失败',
                icon: 'none',
            });
            this.setData({ isLoading: false });
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
        wx.navigateTo({
            url: '/pages/chat/chat',
        });
    },
    /**
     * 跳转到音频生成页面
     */
    goToGenerate() {
        wx.navigateTo({
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
        wx.navigateTo({
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
     * 播放音频
     */
    playAudio(e) {
        const audio = e.currentTarget.dataset.audio;
        // 这里应该实现音频播放逻辑
        wx.showToast({
            title: `播放: ${audio.title}`,
            icon: 'none',
        });
        // 可以调用全局音频播放器
        const app = getApp();
        if (app.globalData.audioPlayer) {
            // 播放音频
        }
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
