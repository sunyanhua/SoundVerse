// 加载组件
Component({
    /**
     * 组件的属性列表
     */
    properties: {
        // 加载文本
        text: {
            type: String,
            value: '加载中...',
        },
        // 是否显示加载动画
        showSpinner: {
            type: Boolean,
            value: true,
        },
        // 自定义样式类
        customClass: {
            type: String,
            value: '',
        },
    },
    /**
     * 组件的初始数据
     */
    data: {},
    /**
     * 组件的方法列表
     */
    methods: {},
});
