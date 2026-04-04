// 生成页面逻辑
Page({
    /**
     * 页面的初始数据
     */
    data: {
        isLoading: false,
        prompt: '',
        generatedAudios: [],
        isGenerating: false,
    },
    /**
     * 生命周期函数--监听页面加载
     */
    onLoad() {
        // 页面加载逻辑
    },
    /**
     * 输入提示词
     */
    onInputPrompt(e) {
        this.setData({
            prompt: e.detail.value
        });
    },
    /**
     * 生成音频
     */
    generateAudio() {
        if (!this.data.prompt.trim()) {
            wx.showToast({
                title: '请输入提示词',
                icon: 'none'
            });
            return;
        }
        wx.showToast({
            title: '生成功能开发中',
            icon: 'none'
        });
    },
    /**
     * 播放生成的音频
     */
    playAudio(e) {
        const index = e.currentTarget.dataset.index;
        const audio = this.data.generatedAudios[index];
        wx.showToast({
            title: '播放功能开发中',
            icon: 'none'
        });
    },
    /**
     * 页面相关事件处理函数--监听用户下拉动作
     */
    onPullDownRefresh() {
        wx.stopPullDownRefresh();
    },
});
