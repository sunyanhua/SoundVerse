"use strict";
/**
 * 小程序环境配置
 * 支持 local (本机开发), dev (公网测试), prod (正式上线) 三个环境
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.getEnvInfo = exports.clearLocalBaseUrl = exports.setLocalBaseUrl = exports.clearManualEnvironment = exports.setManualEnvironment = exports.getBaseUrl = exports.getCurrentEnvConfig = exports.ENV_CONFIG = void 0;
// 环境配置映射
exports.ENV_CONFIG = {
    local: {
        name: 'local',
        baseUrl: 'http://localhost:8000',
        description: '本机开发环境'
    },
    dev: {
        name: 'dev',
        baseUrl: 'https://soundverse.vbegin.com.cn/api',
        description: '公网测试环境'
    },
    prod: {
        name: 'prod',
        baseUrl: 'https://soundverse.vbegin.com.cn/api',
        description: '正式上线环境'
    }
};
// 微信小程序账号环境映射
const WECHAT_ENV_MAP = {
    'develop': 'local',
    'trial': 'dev',
    'release': 'prod' // 正式版
};
// 获取当前环境配置
function getCurrentEnvConfig() {
    var _a;
    try {
        // 1. 首先检查本地存储的手动覆盖设置
        const manualEnv = wx.getStorageSync('manual_env');
        if (manualEnv && exports.ENV_CONFIG[manualEnv]) {
            console.log(`使用手动指定的环境: ${manualEnv}`);
            const config = Object.assign({}, exports.ENV_CONFIG[manualEnv]);
            // 如果是local环境，使用自定义baseUrl
            if (manualEnv === 'local') {
                config.baseUrl = getLocalBaseUrl();
            }
            return config;
        }
        // 2. 获取微信账号信息判断环境
        const accountInfo = wx.getAccountInfoSync();
        const wechatEnv = ((_a = accountInfo.miniProgram) === null || _a === void 0 ? void 0 : _a.envVersion) || 'develop';
        const mappedEnv = WECHAT_ENV_MAP[wechatEnv] || 'local';
        console.log(`微信环境: ${wechatEnv}, 映射到: ${mappedEnv}`);
        const config = Object.assign({}, exports.ENV_CONFIG[mappedEnv]);
        // 如果是local环境，使用自定义baseUrl
        if (mappedEnv === 'local') {
            config.baseUrl = getLocalBaseUrl();
        }
        return config;
    }
    catch (error) {
        console.error('获取环境配置失败，使用默认local环境:', error);
        const config = Object.assign({}, exports.ENV_CONFIG.local);
        config.baseUrl = getLocalBaseUrl();
        return config;
    }
}
exports.getCurrentEnvConfig = getCurrentEnvConfig;
// 获取当前环境的BASE_URL
function getBaseUrl() {
    return getCurrentEnvConfig().baseUrl;
}
exports.getBaseUrl = getBaseUrl;
// 设置手动环境（用于开发者工具中强制指定）
function setManualEnvironment(env) {
    if (!exports.ENV_CONFIG[env]) {
        console.error(`无效的环境类型: ${env}`);
        return;
    }
    wx.setStorageSync('manual_env', env);
    console.log(`已手动设置环境为: ${env}, BASE_URL: ${exports.ENV_CONFIG[env].baseUrl}`);
}
exports.setManualEnvironment = setManualEnvironment;
// 清除手动环境设置
function clearManualEnvironment() {
    wx.removeStorageSync('manual_env');
    console.log('已清除手动环境设置，将使用自动检测');
}
exports.clearManualEnvironment = clearManualEnvironment;
// 设置local环境的自定义baseUrl（用于指定本机IP）
function setLocalBaseUrl(baseUrl) {
    if (!baseUrl.startsWith('http')) {
        console.error('baseUrl必须以http://或https://开头');
        return;
    }
    wx.setStorageSync('local_base_url', baseUrl);
    console.log(`已设置local环境baseUrl为: ${baseUrl}`);
}
exports.setLocalBaseUrl = setLocalBaseUrl;
// 清除local环境自定义baseUrl
function clearLocalBaseUrl() {
    wx.removeStorageSync('local_base_url');
    console.log('已清除local环境自定义baseUrl，使用默认值');
}
exports.clearLocalBaseUrl = clearLocalBaseUrl;
// 获取local环境的baseUrl（优先使用自定义值）
function getLocalBaseUrl() {
    const customUrl = wx.getStorageSync('local_base_url');
    if (customUrl && customUrl.startsWith('http')) {
        return customUrl;
    }
    return exports.ENV_CONFIG.local.baseUrl;
}
// 获取当前环境信息（用于调试）
function getEnvInfo() {
    const config = getCurrentEnvConfig();
    const manualEnv = wx.getStorageSync('manual_env');
    const customLocalUrl = wx.getStorageSync('local_base_url');
    return {
        currentEnv: config.name,
        baseUrl: config.baseUrl,
        description: config.description,
        isManual: !!manualEnv && manualEnv === config.name,
        isCustomLocalUrl: config.name === 'local' && !!customLocalUrl
    };
}
exports.getEnvInfo = getEnvInfo;
