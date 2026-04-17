import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Auth from './components/Auth';
import Layout from './components/Layout';
import UploadStudio from './pages/UploadStudio';
import Library from './pages/Library';
import AILab from './pages/AILab';
import PromptManager from './pages/PromptManager';

function AppContent() {
  const { user, loading } = useAuth();

  // 从 URL 参数初始化当前页面
  const getInitialPage = () => {
    const params = new URLSearchParams(window.location.search);
    const page = params.get('page');
    return page || 'upload';
  };

  const [currentPage, setCurrentPage] = useState(getInitialPage);

  // 监听 URL 变化
  useEffect(() => {
    const handleUrlChange = () => {
      const params = new URLSearchParams(window.location.search);
      const page = params.get('page');
      if (page && ['upload', 'library', 'ai-lab', 'prompts'].includes(page)) {
        setCurrentPage(page);
      }
    };

    // 监听 popstate 事件（浏览器前进/后退）
    window.addEventListener('popstate', handleUrlChange);
    return () => window.removeEventListener('popstate', handleUrlChange);
  }, []);

  // 页面切换时更新 URL
  const handleNavigate = (page: string) => {
    setCurrentPage(page);
    const url = new URL(window.location.href);
    url.searchParams.set('page', page);
    window.history.pushState({}, '', url.toString());
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 flex items-center justify-center">
        <div className="text-white text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent mb-4"></div>
          <p>加载中...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Auth />;
  }

  return (
    <Layout currentPage={currentPage} onNavigate={handleNavigate}>
      {currentPage === 'upload' && <UploadStudio />}
      {currentPage === 'library' && <Library />}
      {currentPage === 'ai-lab' && <AILab />}
      {currentPage === 'prompts' && <PromptManager />}
    </Layout>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
