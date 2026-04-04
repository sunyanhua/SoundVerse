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
        // 是否自动播放
        autoplay: {
            type: Boolean,
            value: false,
        },
    },
    /**
     * 属性监听器
     */
    observers: {
        'audioUrl, autoplay': function (audioUrl, autoplay) {
            // 当音频URL变化且自动播放开启时，尝试自动播放
            if (audioUrl && autoplay) {
                // 确保音频上下文已初始化
                if (!this.data.audioContext) {
                    this.initAudioContext();
                }
                const audioContext = this.data.audioContext;
                if (!audioContext) {
                    return;
                }
                // 如果音频源已相同且正在播放，则无需操作
                if (audioContext.src === audioUrl && this.data.isPlaying) {
                    return;
                }
                // 设置音频源
                audioContext.src = audioUrl;
                // 延迟播放以确保音频已加载
                setTimeout(() => {
                    audioContext.play().catch((err) => {
                        console.error('自动播放失败:', err);
                        // 自动播放失败时不显示错误，可能需用户交互
                    });
                }, 300);
            }
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
        audioContext: null,
    },
    lifetimes: {
        // 生命周期函数
        attached() {
            this.initAudioContext();
            // 组件挂载后检查是否需要自动播放
            if (this.properties.audioUrl && this.properties.autoplay && this.data.audioContext) {
                // 延迟播放以确保音频已加载
                setTimeout(() => {
                    if (this.data.audioContext && !this.data.isPlaying) {
                        this.data.audioContext.src = this.properties.audioUrl;
                        this.data.audioContext.play().catch((err) => {
                            console.error('组件挂载时自动播放失败:', err);
                        });
                    }
                }, 300);
            }
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
            }
            else {
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
        onSliderChange(e) {
            const value = e.detail.value;
            this.seekTo(value);
        },
        /**
         * 滑块拖动中
         */
        onSliderChanging(e) {
            // 可以在这里实现预览功能
        },
        /**
         * 跳转到指定时间
         */
        seekTo(time) {
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
        formatTime(seconds) {
            if (seconds <= 0)
                return '00:00';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        },
        /**
         * 格式化时长（秒 -> 可读格式）
         */
        formatDuration(seconds) {
            if (seconds <= 0)
                return '0秒';
            if (seconds < 60) {
                return `${seconds}秒`;
            }
            else if (seconds < 3600) {
                const mins = Math.floor(seconds / 60);
                const secs = seconds % 60;
                return `${mins}分${secs > 0 ? `${secs}秒` : ''}`;
            }
            else {
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
        setAudioUrl(url) {
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
