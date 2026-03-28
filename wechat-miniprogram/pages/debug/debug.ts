// debug页面 - 环境调试工具
import { getEnvInfo, setManualEnvironment, clearManualEnvironment, setLocalBaseUrl, clearLocalBaseUrl } from '../../config';

Page({
  data: {
    envInfo: null as any,
    customLocalUrl: ''
  },

  onLoad() {
    this.loadEnvInfo();
    // 读取已保存的自定义local URL
    const savedUrl = wx.getStorageSync('local_base_url') || '';
    this.setData({ customLocalUrl: savedUrl });
  },

  loadEnvInfo() {
    const envInfo = getEnvInfo();
    this.setData({ envInfo });
  },

  // 处理自定义URL输入
  onCustomLocalUrlInput(e: any) {
    this.setData({
      customLocalUrl: e.detail.value
    });
  },

  // 手动切换环境
  switchToLocal() {
    setManualEnvironment('local');
    this.loadEnvInfo();
    wx.showToast({ title: '已切换到local环境' });
  },

  switchToDev() {
    setManualEnvironment('dev');
    this.loadEnvInfo();
    wx.showToast({ title: '已切换到dev环境' });
  },

  switchToProd() {
    setManualEnvironment('prod');
    this.loadEnvInfo();
    wx.showToast({ title: '已切换到prod环境' });
  },

  // 设置自定义local baseUrl（指定本机IP）
  setCustomLocalUrl() {
    const { customLocalUrl } = this.data;
    if (!customLocalUrl) {
      wx.showToast({ title: '请输入URL', icon: 'none' });
      return;
    }
    if (!customLocalUrl.startsWith('http')) {
      wx.showToast({ title: 'URL必须以http://或https://开头', icon: 'none' });
      return;
    }
    setLocalBaseUrl(customLocalUrl);
    this.loadEnvInfo();
    wx.showToast({ title: '已设置自定义local URL' });
  },

  // 清除自定义local URL
  clearCustomLocalUrl() {
    clearLocalBaseUrl();
    this.setData({ customLocalUrl: '' });
    this.loadEnvInfo();
    wx.showToast({ title: '已清除自定义local URL' });
  },

  // 清除手动设置
  clearManual() {
    clearManualEnvironment();
    this.loadEnvInfo();
    wx.showToast({ title: '已恢复自动检测' });
  },

  // 测试API连接
  testApiConnection() {
    // 调用API测试接口
    const { envInfo } = this.data;
    wx.request({
      url: `${envInfo.baseUrl}/health`,
      success: (res) => {
        wx.showToast({ title: 'API连接成功' });
        console.log('API响应:', res.data);
      },
      fail: (err) => {
        wx.showToast({ title: 'API连接失败', icon: 'none' });
        console.error('API连接错误:', err);
      }
    });
  }
})