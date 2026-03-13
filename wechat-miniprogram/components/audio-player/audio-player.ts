// 音频播放器组件
Component({
  /**
   * 组件的属性列表
   */
  properties: {
    // 音频信息
    audioUrl: {
      type: String,
      value: '',
    },
    title: {
      type: String,
      value: '音频',
    },
    duration: {
      type: Number,
      value: 0,
    },
    // 状态
    isFavorite: {
      type: Boolean,
      value: false,
    },
    customClass: {
      type: String,
      value: '',
    },
  },

  /**
   * 组件的初始数据
   */
  data: {
    isPlaying: false,
    currentTime: 0,
    loading: false,
    error: '',
    audioContext: null as any,
  },

  lifetimes: {
    // 生命周期函数
    attached() {
      this.initAudioContext();
    },

    detached() {
      this.destroyAudioContext();
    },
  },

  /**
   * 组件的方法列表
   */
  methods: {
    /**
     * 初始化音频上下文
     */
    initAudioContext() {
      if (this.data.audioContext) {
        return;
      }

      const audioContext = wx.createInnerAudioContext();

      // 设置音频源
      if (this.properties.audioUrl) {
        audioContext.src = this.properties.audioUrl;
      }

      // 监听事件
      audioContext.onPlay(() => {
        this.setData({ isPlaying: true, error: '' });
      });

      audioContext.onPause(() => {
        this.setData({ isPlaying: false });
      });

      audioContext.onStop(() => {
        this.setData({ isPlaying: false, currentTime: 0 });
      });

      audioContext.onEnded(() => {
        this.setData({ isPlaying: false, currentTime: 0 });
        this.triggerEvent('ended');
      });

      audioContext.onTimeUpdate(() => {
        this.setData({
          currentTime: Math.floor(audioContext.currentTime),
        });
      });

      audioContext.onError((err) => {
        console.error('音频播放错误:', err);
        this.setData({
          error: `播放失败: ${err.errMsg}`,
          isPlaying: false,
          loading: false,
        });
        this.triggerEvent('error', err);
      });

      audioContext.onWaiting(() => {
        this.setData({ loading: true });
      });

      audioContext.onCanplay(() => {
        this.setData({ loading: false });
      });

      this.setData({ audioContext });
    },

    /**
     * 销毁音频上下文
     */
    destroyAudioContext() {
      if (this.data.audioContext) {
        this.data.audioContext.destroy();
        this.setData({ audioContext: null });
      }
    },

    /**
     * 切换播放/暂停
     */
    togglePlay() {
      if (!this.data.audioContext) {
        this.initAudioContext();
      }

      const { audioContext, isPlaying } = this.data;

      if (isPlaying) {
        audioContext.pause();
      } else {
        // 如果音频源未设置，使用properties中的audioUrl
        if (!audioContext.src && this.properties.audioUrl) {
          audioContext.src = this.properties.audioUrl;
        }

        audioContext.play().catch((err) => {
          console.error('播放失败:', err);
          this.setData({ error: '播放失败，请检查网络或音频地址' });
        });
      }
    },

    /**
     * 滑块值改变
     */
    onSliderChange(e: any) {
      const value = e.detail.value;
      this.seekTo(value);
    },

    /**
     * 滑块拖动中
     */
    onSliderChanging(e: any) {
      // 可以在这里实现预览功能
    },

    /**
     * 跳转到指定时间
     */
    seekTo(time: number) {
      if (this.data.audioContext) {
        this.data.audioContext.seek(time);
        this.setData({ currentTime: time });
      }
    },

    /**
     * 收藏音频
     */
    onFavorite() {
      const isFavorite = !this.data.isFavorite;
      this.setData({ isFavorite });
      this.triggerEvent('favorite', { isFavorite });
    },

    /**
     * 分享音频
     */
    onShare() {
      this.triggerEvent('share');
    },

    /**
     * 下载音频
     */
    onDownload() {
      this.triggerEvent('download');
    },

    /**
     * 重试播放
     */
    retry() {
      this.setData({ error: '', loading: true });
      this.initAudioContext();

      if (this.data.audioContext) {
        this.data.audioContext.src = this.properties.audioUrl;
        this.data.audioContext.play().catch((err) => {
          this.setData({ error: '重试失败', loading: false });
        });
      }
    },

    /**
     * 格式化时间（秒 -> MM:SS）
     */
    formatTime(seconds: number): string {
      if (seconds <= 0) return '00:00';

      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);

      return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    },

    /**
     * 格式化时长（秒 -> 可读格式）
     */
    formatDuration(seconds: number): string {
      if (seconds <= 0) return '0秒';

      if (seconds < 60) {
        return `${seconds}秒`;
      } else if (seconds < 3600) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}分${secs > 0 ? `${secs}秒` : ''}`;
      } else {
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        return `${hours}小时${mins > 0 ? `${mins}分` : ''}`;
      }
    },

    /**
     * 外部调用：播放
     */
    play() {
      if (!this.data.isPlaying) {
        this.togglePlay();
      }
    },

    /**
     * 外部调用：暂停
     */
    pause() {
      if (this.data.isPlaying) {
        this.togglePlay();
      }
    },

    /**
     * 外部调用：停止
     */
    stop() {
      if (this.data.audioContext) {
        this.data.audioContext.stop();
        this.setData({ isPlaying: false, currentTime: 0 });
      }
    },

    /**
     * 外部调用：设置音频源
     */
    setAudioUrl(url: string) {
      if (this.data.audioContext) {
        const wasPlaying = this.data.isPlaying;

        if (wasPlaying) {
          this.data.audioContext.stop();
        }

        this.data.audioContext.src = url;

        if (wasPlaying) {
          this.data.audioContext.play();
        }
      }

      this.setData({ audioUrl: url });
    },
  },
});