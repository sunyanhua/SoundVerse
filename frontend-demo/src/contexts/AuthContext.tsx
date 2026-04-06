import { createContext, useContext, useState, useEffect } from 'react';
import { MockUser } from '../lib/api';

const DEMO_USER: MockUser = {
  id: 'demo-user-001',
  email: 'demo@soundverse.ai',
  name: 'Demo 用户',
};

interface AuthContextType {
  user: MockUser | null;
  loading: boolean;
  signIn: (email?: string, password?: string) => Promise<void>;
  signUp: (email?: string, password?: string) => Promise<void>;
  signOut: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MockUser | null>(null);
  const [loading, setLoading] = useState(true);

  // 检查本地存储的登录状态
  useEffect(() => {
    const storedUser = localStorage.getItem('soundverse_user');
    if (storedUser) {
      setUser(DEMO_USER);
    }
    setLoading(false);
  }, []);

  // demo模式：忽略参数，直接登录
  const signIn = async (_email?: string, _password?: string) => {
    setUser(DEMO_USER);
    localStorage.setItem('soundverse_user', JSON.stringify(DEMO_USER));
  };

  const signUp = async (_email?: string, _password?: string) => {
    // demo模式：注册等同于登录
    setUser(DEMO_USER);
    localStorage.setItem('soundverse_user', JSON.stringify(DEMO_USER));
  };

  const signOut = async () => {
    setUser(null);
    localStorage.removeItem('soundverse_user');
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      signIn,
      signUp,
      signOut,
      isAuthenticated: !!user
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
