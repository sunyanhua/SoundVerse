// 上传页面逻辑
Page({
  /**
   * 页面的初始数据
   */
  data: {
    isLoading: false,
    uploadProgress: 0,
    fileList: [] as any[],
  },

  /**
   * 生命周期函数--监听页面加载
   */
  onLoad() {
    // 页面加载逻辑
  },

  /**
   * 选择文件
   */
  chooseFile() {
    wx.showToast({
      title: '上传功能开发中',
      icon: 'none'
    });
  },

  /**
   * 上传文件
   */
  uploadFile() {
    wx.showToast({
      title: '上传功能开发中',
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