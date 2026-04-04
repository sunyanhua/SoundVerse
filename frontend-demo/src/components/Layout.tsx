import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Upload, Library, Sparkles, Menu, X, LogOut, ChevronLeft, ChevronRight, Mic2 } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
  currentPage: string;
  onNavigate: (page: string) => void;
}

export default function Layout({ children, currentPage, onNavigate }: LayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, signOut } = useAuth();

  const menuItems = [
    { id: 'upload', label: '音频工坊', icon: Upload },
    { id: 'library', label: '精选语弹库', icon: Library },
    { id: 'ai-lab', label: 'AI 对话实验室', icon: Sparkles },
  ];

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  return (
    <div className="h-screen flex bg-slate-50 overflow-hidden">
      <aside
        className={`${
          sidebarCollapsed ? 'w-20' : 'w-64'
        } bg-gradient-to-b from-slate-900 to-slate-800 text-white transition-all duration-300 ease-in-out flex flex-col shadow-xl hidden md:flex`}
      >
        <div className="p-4 border-b border-slate-700 flex items-center justify-between">
          {!sidebarCollapsed ? (
            <div className="flex items-center">
              <div className="bg-gradient-to-br from-cyan-400 to-blue-500 p-2 rounded-lg shadow-lg flex-shrink-0">
                <Mic2 className="w-6 h-6 text-white" />
              </div>
              <span className="ml-2 font-bold text-lg">听听·原声态</span>
            </div>
          ) : (
            <div className="flex items-center justify-center w-full">
              <div className="bg-gradient-to-br from-cyan-400 to-blue-500 p-2 rounded-lg shadow-lg">
                <Mic2 className="w-6 h-6 text-white" />
              </div>
            </div>
          )}
          {!sidebarCollapsed && (
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="p-1.5 rounded-lg hover:bg-slate-700 text-gray-400 transition-all flex-shrink-0"
              title="收起侧边栏"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
          )}
        </div>

        {sidebarCollapsed && (
          <div className="px-2 py-3 border-b border-slate-700">
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="w-full p-2 rounded-lg hover:bg-slate-700 text-gray-400 transition-all flex items-center justify-center"
              title="展开侧边栏"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        <nav className="flex-1 p-4 space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center ${
                  sidebarCollapsed ? 'justify-center' : 'justify-start'
                } p-3 rounded-lg transition-all ${
                  currentPage === item.id
                    ? 'bg-blue-500 text-white shadow-lg'
                    : 'hover:bg-slate-700 text-gray-300'
                }`}
                title={sidebarCollapsed ? item.label : undefined}
              >
                <Icon className="w-5 h-5" />
                {!sidebarCollapsed && <span className="ml-3">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-700 space-y-3">
          {!sidebarCollapsed && user && (
            <div className="text-sm text-gray-300 px-3 py-2 bg-slate-700/50 rounded-lg truncate">
              {user.email}
            </div>
          )}

          <button
            onClick={handleSignOut}
            className={`w-full flex items-center ${
              sidebarCollapsed ? 'justify-center' : 'justify-start'
            } p-3 rounded-lg hover:bg-red-500/20 text-gray-300 hover:text-red-400 transition-all`}
            title={sidebarCollapsed ? '退出登录' : undefined}
          >
            <LogOut className="w-5 h-5" />
            {!sidebarCollapsed && <span className="ml-3">退出登录</span>}
          </button>
        </div>
      </aside>

      <div className="md:hidden fixed top-0 left-0 right-0 bg-slate-900 text-white z-50 shadow-lg">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center">
            <div className="bg-gradient-to-br from-cyan-400 to-blue-500 p-2 rounded-lg shadow-lg">
              <Mic2 className="w-5 h-5 text-white" />
            </div>
            <span className="ml-2 font-bold">听听·原声态</span>
          </div>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="border-t border-slate-700 p-4 space-y-2">
            {menuItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    onNavigate(item.id);
                    setMobileMenuOpen(false);
                  }}
                  className={`w-full flex items-center p-3 rounded-lg transition-all ${
                    currentPage === item.id
                      ? 'bg-blue-500 text-white'
                      : 'hover:bg-slate-800 text-gray-300'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="ml-3">{item.label}</span>
                </button>
              );
            })}
            <button
              onClick={handleSignOut}
              className="w-full flex items-center p-3 rounded-lg hover:bg-red-500/20 text-gray-300 hover:text-red-400 transition-all"
            >
              <LogOut className="w-5 h-5" />
              <span className="ml-3">退出登录</span>
            </button>
          </div>
        )}
      </div>

      <main className="flex-1 overflow-auto md:pt-0 pt-16">
        {children}
      </main>
    </div>
  );
}
