// 个人中心页面逻辑
Page({
    /**
     * 页面的初始数据
     */
    data: {
        userInfo: null,
        stats: {
            chatCount: 0,
            generateCount: 0,
            favoriteCount: 0,
            uploadCount: 0,
        },
        menuItems: [
            { icon: '💬', title: '我的聊天', subTitle: '查看历史对话' },
            { icon: '🎵', title: '我的音频', subTitle: '收藏和上传的音频' },
            { icon: '⚙️', title: '设置', subTitle: '偏好设置与账号管理' },
            { icon: '📱', title: '关于我们', subTitle: '了解听听·原声态' },
            { icon: '❓', title: '帮助与反馈', subTitle: '使用帮助与问题反馈' },
        ],
    },
    /**
     * 生命周期函数--监听页面加载
     */
    onLoad() {
        this.loadUserInfo();
    },
    /**
     * 生命周期函数--监听页面显示
     */
    onShow() {
        this.loadUserInfo();
    },
    /**
     * 加载用户信息
     */
    loadUserInfo() {
        const userInfo = wx.getStorageSync('userInfo');
        if (userInfo) {
            this.setData({ userInfo });
            // 模拟统计数据
            this.setData({
                stats: {
                    chatCount: 12,
                    generateCount: 5,
                    favoriteCount: 8,
                    uploadCount: 3,
                }
            });
        }
    },
    /**
     * 点击菜单项
     */
    onMenuItemTap(e) {
        const index = e.currentTarget.dataset.index;
        const item = this.data.menuItems[index];
        wx.showToast({
            title: `${item.title}功能开发中`,
            icon: 'none'
        });
    },
    /**
     * 点击登录/用户信息
     */
    onUserInfoTap() {
        if (!this.data.userInfo) {
            // 跳转到登录页面
            wx.navigateTo({
                url: '/pages/login/login'
            });
        }
    },
    /**
     * 退出登录
     */
    logout() {
        wx.showModal({
            title: '确认退出',
            content: '确定要退出登录吗？',
            success: (res) => {
                if (res.confirm) {
                    wx.removeStorageSync('token');
                    wx.removeStorageSync('userInfo');
                    this.setData({ userInfo: null });
                    wx.showToast({
                        title: '已退出登录',
                        icon: 'success'
                    });
                }
            }
        });
    },
    /**
     * 页面相关事件处理函数--监听用户下拉动作
     */
    onPullDownRefresh() {
        this.loadUserInfo();
        wx.stopPullDownRefresh();
    },
});
