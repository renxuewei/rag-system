import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Chat from './pages/Chat';
import Documents from './pages/Documents';
import Admin from './pages/Admin';
import Layout from './components/Layout';
import { verifyToken } from './lib/api';

export type Page = 'login' | 'chat' | 'documents' | 'admin';

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('login');
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [isVerifying, setIsVerifying] = useState(true);

  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setTheme('dark');
    }
  }, []);

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const result = await verifyToken();
          if (result.valid) {
            setCurrentPage('chat');
          } else {
            localStorage.removeItem('token');
          }
        } catch (error) {
          console.error('Token verification failed:', error);
          localStorage.removeItem('token');
        }
      }
      setIsVerifying(false);
    };

    checkAuth();
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  if (isVerifying) {
    return (
      <div className="h-full w-full flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-[var(--color-text-sec)]">Loading...</p>
        </div>
      </div>
    );
  }

  if (currentPage === 'login') {
    return <Login onLogin={() => setCurrentPage('chat')} />;
  }

  return (
    <Layout 
      currentPage={currentPage} 
      onNavigate={setCurrentPage} 
      theme={theme} 
      toggleTheme={toggleTheme}
    >
      {currentPage === 'chat' && <Chat />}
      {currentPage === 'documents' && <Documents />}
      {currentPage === 'admin' && <Admin />}
    </Layout>
  );
}
