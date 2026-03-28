/**
 * 小程序环境配置
 * 支持 local (本机开发), dev (公网测试), prod (正式上线) 三个环境
 */

// 环境类型定义
export type Environment = 'local' | 'dev' | 'prod';

// 环境配置接口
export interface EnvConfig {
  name: Environment;
  baseUrl: string;
  description: string;
}

// 环境配置映射
export const ENV_CONFIG: Record<Environment, EnvConfig> = {
  local: {
    name: 'local',
    baseUrl: 'http://localhost:8000', // 默认值，可通过setLocalBaseUrl覆盖
    description: '本机开发环境'
  },
  dev: {
    name: 'dev',
    baseUrl: 'http://dev-api.soundverse.example.com',
    description: '公网测试环境'
  },
  prod: {
    name: 'prod',
    baseUrl: 'https://api.soundverse.example.com',
    description: '正式上线环境'
  }
};

// 微信小程序账号环境映射
const WECHAT_ENV_MAP: Record<string, Environment> = {
  'develop': 'local',    // 开发者工具
  'trial': 'dev',        // 体验版
  'release': 'prod'      // 正式版
};

// 获取当前环境配置
export function getCurrentEnvConfig(): EnvConfig {
  try {
    // 1. 首先检查本地存储的手动覆盖设置
    const manualEnv = wx.getStorageSync('manual_env') as Environment;
    if (manualEnv && ENV_CONFIG[manualEnv]) {
      console.log(`使用手动指定的环境: ${manualEnv}`);
      const config = { ...ENV_CONFIG[manualEnv] };
      // 如果是local环境，使用自定义baseUrl
      if (manualEnv === 'local') {
        config.baseUrl = getLocalBaseUrl();
      }
      return config;
    }

    // 2. 获取微信账号信息判断环境
    const accountInfo = wx.getAccountInfoSync();
    const wechatEnv = accountInfo.miniProgram?.envVersion || 'develop';
    const mappedEnv = WECHAT_ENV_MAP[wechatEnv] || 'local';

    console.log(`微信环境: ${wechatEnv}, 映射到: ${mappedEnv}`);
    const config = { ...ENV_CONFIG[mappedEnv] };
    // 如果是local环境，使用自定义baseUrl
    if (mappedEnv === 'local') {
      config.baseUrl = getLocalBaseUrl();
    }
    return config;
  } catch (error) {
    console.error('获取环境配置失败，使用默认local环境:', error);
    const config = { ...ENV_CONFIG.local };
    config.baseUrl = getLocalBaseUrl();
    return config;
  }
}

// 获取当前环境的BASE_URL
export function getBaseUrl(): string {
  return getCurrentEnvConfig().baseUrl;
}

// 设置手动环境（用于开发者工具中强制指定）
export function setManualEnvironment(env: Environment): void {
  if (!ENV_CONFIG[env]) {
    console.error(`无效的环境类型: ${env}`);
    return;
  }
  wx.setStorageSync('manual_env', env);
  console.log(`已手动设置环境为: ${env}, BASE_URL: ${ENV_CONFIG[env].baseUrl}`);
}

// 清除手动环境设置
export function clearManualEnvironment(): void {
  wx.removeStorageSync('manual_env');
  console.log('已清除手动环境设置，将使用自动检测');
}

// 设置local环境的自定义baseUrl（用于指定本机IP）
export function setLocalBaseUrl(baseUrl: string): void {
  if (!baseUrl.startsWith('http')) {
    console.error('baseUrl必须以http://或https://开头');
    return;
  }
  wx.setStorageSync('local_base_url', baseUrl);
  console.log(`已设置local环境baseUrl为: ${baseUrl}`);
}

// 清除local环境自定义baseUrl
export function clearLocalBaseUrl(): void {
  wx.removeStorageSync('local_base_url');
  console.log('已清除local环境自定义baseUrl，使用默认值');
}

// 获取local环境的baseUrl（优先使用自定义值）
function getLocalBaseUrl(): string {
  const customUrl = wx.getStorageSync('local_base_url') as string;
  if (customUrl && customUrl.startsWith('http')) {
    return customUrl;
  }
  return ENV_CONFIG.local.baseUrl;
}

// 获取当前环境信息（用于调试）
export function getEnvInfo(): {
  currentEnv: Environment;
  baseUrl: string;
  description: string;
  isManual: boolean;
  isCustomLocalUrl: boolean;
} {
  const config = getCurrentEnvConfig();
  const manualEnv = wx.getStorageSync('manual_env') as Environment;
  const customLocalUrl = wx.getStorageSync('local_base_url') as string;

  return {
    currentEnv: config.name,
    baseUrl: config.baseUrl,
    description: config.description,
    isManual: !!manualEnv && manualEnv === config.name,
    isCustomLocalUrl: config.name === 'local' && !!customLocalUrl
  };
}