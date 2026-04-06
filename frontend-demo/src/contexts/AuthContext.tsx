import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../lib/api';

const API_BASE_URL = 'http://localhost:8000/api';

// 预置用户凭据
const PRESET_USERNAME = "admin";
const PRESET_PASSWORD = "soundverse2024";

export interface User {
  id: string;
  nickname: string;
  avatar_url?: string;
  is_admin: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (username?: string, password?: string) => Promise<void>;
  signOut: () => Promise<void>;
  isAuthenticated: boolean;
  token: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 检查本地存储的登录状态
  useEffect(() => {
    const storedToken = localStorage.getItem('soundverse_token');
    if (storedToken) {
      setToken(storedToken);
      // 验证 token 并获取用户信息
      fetchUserInfo(storedToken);
    } else {
      setLoading(false);
    }
  }, []);

  // 获取用户信息
  const fetchUserInfo = async (authToken: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/v1/auth/me`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        // Token 无效，清除登录状态
        localStorage.removeItem('soundverse_token');
        setToken(null);
      }
    } catch (error) {
      console.error('获取用户信息失败:', error);
      localStorage.removeItem('soundverse_token');
      setToken(null);
    } finally {
      setLoading(false);
    }
  };

  // 真实登录
  const signIn = async (username: string = PRESET_USERNAME, password: string = PRESET_PASSWORD) => {
    try {
      const response = await fetch(`${API_BASE_URL}/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '登录失败');
      }

      const data = await response.json();
      const accessToken = data.access_token;

      // 保存 token
      localStorage.setItem('soundverse_token', accessToken);
      setToken(accessToken);

      // 获取用户信息
      await fetchUserInfo(accessToken);
    } catch (error: any) {
      console.error('登录失败:', error);
      throw error;
    }
  };

  // 真实退出
  const signOut = async () => {
    try {
      // 调用后端登出接口（可选）
      if (token) {
        await fetch(`${API_BASE_URL}/v1/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
      }
    } catch (error) {
      console.error('登出请求失败:', error);
    } finally {
      // 清除本地登录状态
      localStorage.removeItem('soundverse_token');
      setToken(null);
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      signIn,
      signOut,
      isAuthenticated: !!user && !!token,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
