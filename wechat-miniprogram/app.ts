// app.ts
App<IAppOption>({
  globalData: {
    userInfo: null,
    token: null,
    baseUrl: 'https://api.soundverse.example.com' // 替换为实际后端地址
  },

  onLaunch() {
    // 初始化时获取本地存储的用户信息
    const token = wx.getStorageSync('token');
    const userInfo = wx.getStorageSync('userInfo');

    if (token && userInfo) {
      this.globalData.token = token;
      this.globalData.userInfo = userInfo;
    }

    // 检查更新
    this.checkUpdate();
  },

  checkUpdate() {
    if (wx.canIUse('getUpdateManager')) {
      const updateManager = wx.getUpdateManager();

      updateManager.onCheckForUpdate((res) => {
        console.log('检查更新结果:', res.hasUpdate);
      });

      updateManager.onUpdateReady(() => {
        wx.showModal({
          title: '更新提示',
          content: '新版本已经准备好，是否重启应用？',
          success: (res) => {
            if (res.confirm) {
              updateManager.applyUpdate();
            }
          }
        });
      });

      updateManager.onUpdateFailed(() => {
        wx.showToast({
          title: '更新失败',
          icon: 'none'
        });
      });
    }
  }
});

// 全局类型定义
interface IAppOption {
  globalData: {
    userInfo: any;
    token: string | null;
    baseUrl: string;
  };
  onLaunch(): void;
  checkUpdate(): void;
}