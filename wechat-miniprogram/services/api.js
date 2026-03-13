"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.checkLogin = exports.handleApiError = exports.uploadFile = exports.del = exports.put = exports.post = exports.get = exports.request = void 0;
// 开发环境API地址（请根据实际情况修改为您的局域网IP）
// 例如：http://192.168.1.100:8000
const BASE_URL = 'http://192.168.1.133:8000'; // 开发环境API地址
// const BASE_URL = 'https://api.soundverse.example.com'; // 生产环境API地址
// 获取请求头
function getHeaders(withAuth = true) {
    const headers = {
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
async function handleResponse(response) {
    const contentType = response.header['Content-Type'] || '';
    if (response.statusCode >= 200 && response.statusCode < 300) {
        let data;
        if (contentType.includes('application/json')) {
            data = response.data;
        }
        else {
            data = response.data;
        }
        return {
            success: true,
            data: data.data || data,
            code: data.code || response.statusCode,
            message: data.message || '请求成功',
        };
    }
    else {
        let errorMessage = `请求失败: ${response.statusCode}`;
        try {
            if (contentType.includes('application/json')) {
                const errorData = response.data;
                errorMessage = errorData.message || errorData.detail || errorMessage;
            }
        }
        catch (e) {
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
async function request(options) {
    const { url, method = 'GET', data, params, headers = {}, withAuth = true, showLoading = true, loadingText = '加载中...', } = options;
    // 显示加载提示
    if (showLoading) {
        wx.showLoading({ title: loadingText, mask: true });
    }
    try {
        // 处理查询参数
        let requestUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`;
        if (params) {
            const queryParams = [];
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
        const requestHeaders = Object.assign(Object.assign({}, getHeaders(withAuth)), headers);
        // 发起请求
        const response = await new Promise((resolve, reject) => {
            wx.request({
                url: requestUrl,
                method: method,
                data: data,
                header: requestHeaders,
                success: resolve,
                fail: reject,
            });
        });
        return await handleResponse(response);
    }
    catch (error) {
        console.error('API请求错误:', error);
        let errorMessage = '网络请求失败';
        if (error.errMsg) {
            if (error.errMsg.includes('timeout')) {
                errorMessage = '请求超时，请检查网络';
            }
            else if (error.errMsg.includes('fail')) {
                errorMessage = '网络连接失败';
            }
        }
        return {
            success: false,
            data: null,
            code: 500,
            message: errorMessage,
        };
    }
    finally {
        if (showLoading) {
            wx.hideLoading();
        }
    }
}
exports.request = request;
// GET请求
async function get(url, params, options) {
    return request(Object.assign({ url, method: 'GET', params }, options));
}
exports.get = get;
// POST请求
async function post(url, data, options) {
    return request(Object.assign({ url, method: 'POST', data }, options));
}
exports.post = post;
// PUT请求
async function put(url, data, options) {
    return request(Object.assign({ url, method: 'PUT', data }, options));
}
exports.put = put;
// DELETE请求
async function del(url, params, options) {
    return request(Object.assign({ url, method: 'DELETE', params }, options));
}
exports.del = del;
// 上传文件
async function uploadFile(url, filePath, formData, options) {
    const { showLoading = true, loadingText = '上传中...' } = options || {};
    if (showLoading) {
        wx.showLoading({ title: loadingText, mask: true });
    }
    try {
        const response = await new Promise((resolve, reject) => {
            wx.uploadFile({
                url: url.startsWith('http') ? url : `${BASE_URL}${url}`,
                filePath,
                name: 'file',
                formData: formData || {},
                header: getHeaders(true),
                success: resolve,
                fail: reject,
            });
        });
        // 解析响应（上传文件返回的可能是字符串）
        let responseData;
        try {
            responseData = JSON.parse(response.data);
        }
        catch (e) {
            responseData = response.data;
        }
        const apiResponse = {
            success: response.statusCode >= 200 && response.statusCode < 300,
            data: responseData,
            code: response.statusCode,
            message: response.statusCode < 300 ? '上传成功' : '上传失败',
        };
        return apiResponse;
    }
    catch (error) {
        console.error('文件上传错误:', error);
        return {
            success: false,
            data: null,
            code: 500,
            message: '文件上传失败',
        };
    }
    finally {
        if (showLoading) {
            wx.hideLoading();
        }
    }
}
exports.uploadFile = uploadFile;
// 处理错误（显示Toast提示）
function handleApiError(response, defaultMessage = '操作失败') {
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
exports.handleApiError = handleApiError;
// 检查登录状态
function checkLogin() {
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
exports.checkLogin = checkLogin;
