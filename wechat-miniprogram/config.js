"use strict";
/**
 * 小程序环境配置
 * 强制锁定生产环境，避免真机测试问题
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.clearLocalBaseUrl = exports.setLocalBaseUrl = exports.clearManualEnvironment = exports.setManualEnvironment = exports.getEnvInfo = exports.resolveAudioUrl = exports.getAudioBaseUrl = exports.getBaseUrl = exports.PROD_CONFIG = exports.FORCE_PROD = void 0;
// 强制生产环境开关 - 设为 true 时，无论当前是开发版还是体验版，都使用生产环境
exports.FORCE_PROD = true;
// 生产环境配置
exports.PROD_CONFIG = {
    name: 'prod',
    baseUrl: 'https://soundverse.vbegin.com.cn/api',
    description: '强制生产环境'
};
// 获取当前环境的BASE_URL
function getBaseUrl() {
    // 如果强制生产环境开关开启，直接返回生产环境URL
    if (exports.FORCE_PROD) {
        console.log('🚨 强制生产环境模式已开启，使用:', exports.PROD_CONFIG.baseUrl);
        return exports.PROD_CONFIG.baseUrl;
    }
    // 以下是保留原有逻辑（当FORCE_PROD=false时使用）
    try {
        // 检查本地存储的手动覆盖设置
        const manualEnv = wx.getStorageSync('manual_env');
        if (manualEnv) {
            console.log(`使用手动指定的环境: ${manualEnv}`);
            // 简化处理，直接返回对应环境的URL
            if (manualEnv === 'local') {
                const customUrl = wx.getStorageSync('local_base_url');
                if (customUrl && customUrl.startsWith('http')) {
                    return customUrl;
                }
                return 'http://localhost:8000';
            }
            else if (manualEnv === 'dev') {
                return 'http://dev-api.soundverse.example.com';
            }
            else {
                return 'https://api.soundverse.example.com';
            }
        }
        // 获取微信账号信息判断环境
        const accountInfo = wx.getAccountInfoSync();
        const wechatEnv = accountInfo.miniProgram?.envVersion || 'develop';
        // 微信环境映射
        if (wechatEnv === 'release') {
            return 'https://api.soundverse.example.com';
        }
        else if (wechatEnv === 'trial') {
            return 'http://dev-api.soundverse.example.com';
        }
        else {
            // develop 或其他
            const customUrl = wx.getStorageSync('local_base_url');
            if (customUrl && customUrl.startsWith('http')) {
                return customUrl;
            }
            return 'http://localhost:8000';
        }
    }
    catch (error) {
        console.error('获取环境配置失败，使用默认生产环境:', error);
        return exports.PROD_CONFIG.baseUrl;
    }
}
exports.getBaseUrl = getBaseUrl;
// 获取音频文件的基础URL（用于音频播放器）
function getAudioBaseUrl() {
    // 音频文件和生产环境API使用相同域名，但路径不同
    // 注意：音频文件可能存储在OSS，这里返回域名部分
    if (exports.FORCE_PROD) {
        return 'https://soundverse.vbegin.com.cn';
    }
    // 非强制模式，根据当前环境返回对应域名
    const baseUrl = getBaseUrl();
    // 从baseUrl中提取域名部分（移除/api路径）
    try {
        const urlObj = new URL(baseUrl);
        return `${urlObj.protocol}//${urlObj.host}`;
    }
    catch (e) {
        console.error('解析baseUrl失败:', e);
        return baseUrl.replace(/\/api\/?$/, ''); // 移除末尾的/api
    }
}
exports.getAudioBaseUrl = getAudioBaseUrl;
// 解析音频URL，如果是相对路径则添加音频基础域名
function resolveAudioUrl(audioUrl) {
    if (!audioUrl) {
        return audioUrl;
    }
    // 如果已经是完整URL，直接返回
    if (audioUrl.startsWith('http://') || audioUrl.startsWith('https://')) {
        return audioUrl;
    }
    // 相对路径，添加音频基础域名
    const audioBaseUrl = getAudioBaseUrl();
    const normalizedBaseUrl = audioBaseUrl.replace(/\/$/, '');
    const normalizedUrl = audioUrl.startsWith('/') ? audioUrl : `/${audioUrl}`;
    const resolvedUrl = `${normalizedBaseUrl}${normalizedUrl}`;
    console.log('🎵 解析音频URL:', { original: audioUrl, resolved: resolvedUrl, audioBaseUrl: audioBaseUrl });
    return resolvedUrl;
}
exports.resolveAudioUrl = resolveAudioUrl;
// 获取当前环境信息（用于调试）
function getEnvInfo() {
    const baseUrl = getBaseUrl();
    const isForceProd = exports.FORCE_PROD;
    return {
        currentEnv: isForceProd ? 'prod (forced)' : 'auto',
        baseUrl: baseUrl,
        description: isForceProd ? '强制生产环境' : '自动检测环境',
        isForceProd: isForceProd
    };
}
exports.getEnvInfo = getEnvInfo;
// 兼容原有API（简化实现）
function setManualEnvironment(env) {
    if (exports.FORCE_PROD) {
        console.log('🚨 强制生产环境模式已开启，手动设置无效');
        return;
    }
    wx.setStorageSync('manual_env', env);
    console.log(`已手动设置环境为: ${env}`);
}
exports.setManualEnvironment = setManualEnvironment;
function clearManualEnvironment() {
    if (exports.FORCE_PROD) {
        console.log('🚨 强制生产环境模式已开启，清除设置无效');
        return;
    }
    wx.removeStorageSync('manual_env');
    console.log('已清除手动环境设置');
}
exports.clearManualEnvironment = clearManualEnvironment;
function setLocalBaseUrl(baseUrl) {
    if (exports.FORCE_PROD) {
        console.log('🚨 强制生产环境模式已开启，设置本地URL无效');
        return;
    }
    if (!baseUrl.startsWith('http')) {
        console.error('baseUrl必须以http://或https://开头');
        return;
    }
    wx.setStorageSync('local_base_url', baseUrl);
    console.log(`已设置local环境baseUrl为: ${baseUrl}`);
}
exports.setLocalBaseUrl = setLocalBaseUrl;
function clearLocalBaseUrl() {
    if (exports.FORCE_PROD) {
        console.log('🚨 强制生产环境模式已开启，清除设置无效');
        return;
    }
    wx.removeStorageSync('local_base_url');
    console.log('已清除local环境自定义baseUrl');
}
exports.clearLocalBaseUrl = clearLocalBaseUrl;