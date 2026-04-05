import { createContext, useContext, useState } from 'react';
import { MockUser } from '../lib/api';

const DEMO_USER: MockUser = {
  id: 'demo-user-001',
  email: 'demo@soundverse.ai',
  name: 'Demo 用户',
};

interface AuthContextType {
  user: MockUser | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user] = useState<MockUser>(DEMO_USER);
  const [loading] = useState(false);

  const signOut = async () => {
    // demo模式无需登出
  };

  return (
    <AuthContext.Provider value={{ user, loading, signOut }}>
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
