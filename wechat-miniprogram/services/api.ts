// API请求封装
import type { RequestOptions, ApiResponse } from '../types/api';
import { getBaseUrl } from '../config';

// 开发环境API地址（请根据实际情况修改为您的局域网IP）
// 例如：http://192.168.1.100:8000
// const BASE_URL = 'https://api.soundverse.example.com'; // 生产环境API地址

// 获取请求头
function getHeaders(withAuth: boolean = true): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  if (withAuth) {
    const token = wx.getStorageSync('token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  return headers;
}

// 处理响应
async function handleResponse<T>(response: any): Promise<ApiResponse<T>> {
  const contentType = response.header['Content-Type'] || '';

  if (response.statusCode >= 200 && response.statusCode < 300) {
    let data: any;

    if (contentType.includes('application/json')) {
      data = response.data;
    } else {
      data = response.data;
    }

    return {
      success: true,
      data: data.data || data,
      code: data.code || response.statusCode,
      message: data.message || '请求成功',
    };
  } else {
    let errorMessage = `请求失败: ${response.statusCode}`;

    try {
      if (contentType.includes('application/json')) {
        const errorData = response.data;
        errorMessage = errorData.message || errorData.detail || errorMessage;
      }
    } catch (e) {
      // 忽略解析错误
    }

    return {
      success: false,
      data: null,
      code: response.statusCode,
      message: errorMessage,
    };
  }
}

// 基础请求方法
export async function request<T>(
  options: RequestOptions
): Promise<ApiResponse<T>> {
  const {
    url,
    method = 'GET',
    data,
    params,
    headers = {},
    withAuth = true,
    showLoading = true,
    loadingText = '加载中...',
  } = options;

  // 显示加载提示
  if (showLoading) {
    wx.showLoading({ title: loadingText, mask: true });
  }

  try {
    // 打印当前运行环境
    try {
      const accountInfo = wx.getAccountInfoSync();
      console.log('当前运行环境:', accountInfo.miniProgram.envVersion);
    } catch (e) {
      console.log('获取运行环境失败:', e);
    }

    // 处理查询参数
    let requestUrl = url.startsWith('http') ? url : '';
    if (!requestUrl) {
      const baseUrl = getBaseUrl();
      // 确保baseUrl不以斜杠结尾，url以斜杠开头
      const normalizedBaseUrl = baseUrl.replace(/\/$/, ''); // 移除末尾斜杠
      const normalizedUrl = url.startsWith('/') ? url : `/${url}`; // 确保url以斜杠开头
      requestUrl = `${normalizedBaseUrl}${normalizedUrl}`;
    }

    if (params) {
      const queryParams: string[] = [];
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
        }
      });

      const queryString = queryParams.join('&');
      if (queryString) {
        requestUrl += `?${queryString}`;
      }
    }

    // 合并请求头
    const requestHeaders = {
      ...getHeaders(withAuth),
      ...headers,
    };

    // 发起请求
    console.log('🚀 [网络请求] 完整地址:', requestUrl);
    const response = await new Promise<any>((resolve, reject) => {
      wx.request({
        url: requestUrl,
        method: method as any,
        data: data,
        header: requestHeaders,
        success: resolve,
        fail: reject,
      });
    });

    return await handleResponse<T>(response);
  } catch (error: any) {
    console.error('API请求错误:', error);

    let errorMessage = '网络请求失败';
    if (error.errMsg) {
      if (error.errMsg.includes('timeout')) {
        errorMessage = '请求超时，请检查网络';
      } else if (error.errMsg.includes('fail')) {
        errorMessage = '网络连接失败';
      }
    }

    return {
      success: false,
      data: null,
      code: 500,
      message: errorMessage,
    };
  } finally {
    if (showLoading) {
      wx.hideLoading();
    }
  }
}

// GET请求
export async function get<T>(
  url: string,
  params?: Record<string, any>,
  options?: Partial<RequestOptions>
): Promise<ApiResponse<T>> {
  return request<T>({
    url,
    method: 'GET',
    params,
    ...options,
  });
}

// POST请求
export async function post<T>(
  url: string,
  data?: any,
  options?: Partial<RequestOptions>
): Promise<ApiResponse<T>> {
  return request<T>({
    url,
    method: 'POST',
    data,
    ...options,
  });
}

// PUT请求
export async function put<T>(
  url: string,
  data?: any,
  options?: Partial<RequestOptions>
): Promise<ApiResponse<T>> {
  return request<T>({
    url,
    method: 'PUT',
    data,
    ...options,
  });
}

// DELETE请求
export async function del<T>(
  url: string,
  params?: Record<string, any>,
  options?: Partial<RequestOptions>
): Promise<ApiResponse<T>> {
  return request<T>({
    url,
    method: 'DELETE',
    params,
    ...options,
  });
}

// 上传文件
export async function uploadFile(
  url: string,
  filePath: string,
  formData?: Record<string, any>,
  options?: Partial<RequestOptions>
): Promise<ApiResponse<any>> {
  const { showLoading = true, loadingText = '上传中...' } = options || {};

  if (showLoading) {
    wx.showLoading({ title: loadingText, mask: true });
  }

  try {
    let uploadUrl = url.startsWith('http') ? url : '';
    if (!uploadUrl) {
      const baseUrl = getBaseUrl();
      // 确保baseUrl不以斜杠结尾，url以斜杠开头
      const normalizedBaseUrl = baseUrl.replace(/\/$/, ''); // 移除末尾斜杠
      const normalizedUrl = url.startsWith('/') ? url : `/${url}`; // 确保url以斜杠开头
      uploadUrl = `${normalizedBaseUrl}${normalizedUrl}`;
    }
    console.log('🚀 [文件上传] 完整地址:', uploadUrl);
    try {
      const accountInfo = wx.getAccountInfoSync();
      console.log('当前运行环境:', accountInfo.miniProgram.envVersion);
    } catch (e) {
      console.log('获取运行环境失败:', e);
    }
    const response = await new Promise<any>((resolve, reject) => {
      wx.uploadFile({
        url: uploadUrl,
        filePath,
        name: 'file',
        formData: formData || {},
        header: getHeaders(true),
        success: resolve,
        fail: reject,
      });
    });

    // 解析响应（上传文件返回的可能是字符串）
    let responseData: any;
    try {
      responseData = JSON.parse(response.data);
    } catch (e) {
      responseData = response.data;
    }

    const apiResponse: ApiResponse<any> = {
      success: response.statusCode >= 200 && response.statusCode < 300,
      data: responseData,
      code: response.statusCode,
      message: response.statusCode < 300 ? '上传成功' : '上传失败',
    };

    return apiResponse;
  } catch (error: any) {
    console.error('文件上传错误:', error);

    return {
      success: false,
      data: null,
      code: 500,
      message: '文件上传失败',
    };
  } finally {
    if (showLoading) {
      wx.hideLoading();
    }
  }
}

// 处理错误（显示Toast提示）
export function handleApiError(
  response: ApiResponse<any>,
  defaultMessage: string = '操作失败'
): boolean {
  if (!response.success) {
    const message = response.message || defaultMessage;
    wx.showToast({
      title: message,
      icon: 'none',
      duration: 2000,
    });
    return true;
  }
  return false;
}

// 检查登录状态
export function checkLogin(): boolean {
  const token = wx.getStorageSync('token');
  const userInfo = wx.getStorageSync('userInfo');

  if (!token || !userInfo) {
    wx.showModal({
      title: '未登录',
      content: '请先登录',
      confirmText: '去登录',
      success: (res) => {
        if (res.confirm) {
          // 跳转到登录页面
          wx.navigateTo({
            url: '/pages/login/login',
          });
        }
      },
    });
    return false;
  }

  return true;
}