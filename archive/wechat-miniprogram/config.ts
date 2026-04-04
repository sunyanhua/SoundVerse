/**
 * 小程序环境配置
 * 强制锁定生产环境，避免真机测试问题
 */

// 强制生产环境开关 - 设为 true 时，无论当前是开发版还是体验版，都使用生产环境
export const FORCE_PROD = true;

// 生产环境配置
export const PROD_CONFIG = {
  name: 'prod' as const,
  baseUrl: 'https://soundverse.vbegin.com.cn', // 生产环境API地址
  description: '强制生产环境'
};

// 获取当前环境的BASE_URL
export function getBaseUrl(): string {
  // 辅助函数：清理URL，确保不以/api结尾
  const cleanUrl = (url: string): string => {
    // 移除末尾的/api和斜杠
    return url.replace(/\/api\/?$/, '').replace(/\/$/, '');
  };

  // 如果强制生产环境开关开启，直接返回生产环境URL
  if (FORCE_PROD) {
    const baseUrl = PROD_CONFIG.baseUrl;
    const cleanedUrl = cleanUrl(baseUrl);
    console.log('🚨 强制生产环境模式已开启，使用:', cleanedUrl);
    return cleanedUrl;
  }

  // 以下是保留原有逻辑（当FORCE_PROD=false时使用）
  try {
    // 检查本地存储的手动覆盖设置
    const manualEnv = wx.getStorageSync('manual_env') as 'local' | 'dev' | 'prod';
    if (manualEnv) {
      console.log(`使用手动指定的环境: ${manualEnv}`);
      // 简化处理，直接返回对应环境的URL
      if (manualEnv === 'local') {
        const customUrl = wx.getStorageSync('local_base_url') as string;
        if (customUrl && customUrl.startsWith('http')) {
          return cleanUrl(customUrl);
        }
        return 'http://localhost:8000';
      } else if (manualEnv === 'dev') {
        return 'http://dev-api.soundverse.example.com';
      } else {
        return 'https://api.soundverse.example.com';
      }
    }

    // 获取微信账号信息判断环境
    const accountInfo = wx.getAccountInfoSync();
    const wechatEnv = accountInfo.miniProgram?.envVersion || 'develop';

    // 微信环境映射
    if (wechatEnv === 'release') {
      return 'https://api.soundverse.example.com';
    } else if (wechatEnv === 'trial') {
      return 'http://dev-api.soundverse.example.com';
    } else {
      // develop 或其他
      const customUrl = wx.getStorageSync('local_base_url') as string;
      if (customUrl && customUrl.startsWith('http')) {
        return cleanUrl(customUrl);
      }
      return 'http://localhost:8000';
    }
  } catch (error) {
    console.error('获取环境配置失败，使用默认生产环境:', error);
    return cleanUrl(PROD_CONFIG.baseUrl);
  }
}

// 获取音频文件的基础URL（用于音频播放器）
export function getAudioBaseUrl(): string {
  // 音频文件和生产环境API使用相同域名，但路径不同
  // 注意：音频文件可能存储在OSS，这里返回域名部分
  if (FORCE_PROD) {
    return 'https://soundverse.vbegin.com.cn';
  }

  // 非强制模式，根据当前环境返回对应域名
  const baseUrl = getBaseUrl();
  // 从baseUrl中提取域名部分（移除/api路径）
  try {
    const urlObj = new URL(baseUrl);
    return `${urlObj.protocol}//${urlObj.host}`;
  } catch (e) {
    console.error('解析baseUrl失败:', e);
    return baseUrl.replace(/\/api\/?$/, ''); // 移除末尾的/api
  }
}

// 解析音频URL，如果是相对路径则添加音频基础域名
export function resolveAudioUrl(audioUrl: string): string {
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
  console.log('🎵 解析音频URL:', { original: audioUrl, resolved: resolvedUrl, audioBaseUrl });
  return resolvedUrl;
}

// 获取当前环境信息（用于调试）
export function getEnvInfo(): {
  currentEnv: string;
  baseUrl: string;
  description: string;
  isForceProd: boolean;
} {
  const baseUrl = getBaseUrl();
  const isForceProd = FORCE_PROD;

  return {
    currentEnv: isForceProd ? 'prod (forced)' : 'auto',
    baseUrl,
    description: isForceProd ? '强制生产环境' : '自动检测环境',
    isForceProd
  };
}

// 兼容原有API（简化实现）
export function setManualEnvironment(env: 'local' | 'dev' | 'prod'): void {
  if (FORCE_PROD) {
    console.log('🚨 强制生产环境模式已开启，手动设置无效');
    return;
  }
  wx.setStorageSync('manual_env', env);
  console.log(`已手动设置环境为: ${env}`);
}

export function clearManualEnvironment(): void {
  if (FORCE_PROD) {
    console.log('🚨 强制生产环境模式已开启，清除设置无效');
    return;
  }
  wx.removeStorageSync('manual_env');
  console.log('已清除手动环境设置');
}

export function setLocalBaseUrl(baseUrl: string): void {
  if (FORCE_PROD) {
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

export function clearLocalBaseUrl(): void {
  if (FORCE_PROD) {
    console.log('🚨 强制生产环境模式已开启，清除设置无效');
    return;
  }
  wx.removeStorageSync('local_base_url');
  console.log('已清除local环境自定义baseUrl');
}