import { useState, FormEvent } from 'react';
import { Bot, Eye, EyeOff } from 'lucide-react';
import { motion } from 'motion/react';
import { login } from '../lib/api';

interface LoginProps {
  onLogin: () => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [tenant, setTenant] = useState('default');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please enter username and password');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      await login(username, password, tenant);
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-full w-full overflow-y-auto flex items-center justify-center bg-gradient-to-br from-[#3B82F6] to-[#1E40AF] p-4">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-[400px] bg-[var(--color-surface)] rounded-xl shadow-2xl p-10"
      >
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-[var(--color-primary)]/10 rounded-full flex items-center justify-center mb-4">
            <Bot className="w-8 h-8 text-[var(--color-primary)]" />
          </div>
          <h1 className="text-[32px] font-bold text-[var(--color-primary)] leading-[40px] text-center">
            RAG Knowledge Base
          </h1>
          <p className="text-base text-[var(--color-text-sec)] text-center mt-2">
            Enterprise Intelligent Q&A System
          </p>
        </div>

        {error && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-4 p-2 bg-[var(--color-error)]/10 text-[var(--color-error)] text-sm rounded-md text-center"
          >
            {error}
          </motion.div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Username</label>
            <input 
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              disabled={isLoading}
              className="w-full h-10 px-3 border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20 transition-all text-sm disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Password</label>
            <div className="relative">
              <input 
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                disabled={isLoading}
                className="w-full h-10 pl-3 pr-10 border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20 transition-all text-sm disabled:opacity-50"
              />
              <button 
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                disabled={isLoading}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-sec)] hover:text-[var(--color-text-main)] disabled:opacity-50"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs text-[var(--color-text-sec)] mb-1 font-medium">Tenant ID</label>
            <input 
              type="text"
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
              placeholder="Default tenant"
              disabled={isLoading}
              className="w-full h-10 px-3 border border-[var(--color-border)] rounded-md bg-[var(--color-surface)] text-[var(--color-text-main)] placeholder-[var(--color-text-mut)] focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary)]/20 transition-all text-sm disabled:opacity-50"
            />
          </div>

          <button 
            type="submit"
            disabled={isLoading}
            className="w-full h-10 mt-6 bg-[var(--color-primary)] text-white text-base font-semibold rounded-md hover:bg-[var(--color-primary-hover)] active:bg-[var(--color-primary-active)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 shadow-md shadow-[var(--color-primary)]/20 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--color-border)]">
          <p className="text-xs text-[var(--color-text-sec)] text-center mb-1">Demo accounts:</p>
          <p className="text-[11px] text-[var(--color-text-mut)] text-center">
            admin / admin123 | doc_admin / docadmin123 | user / user123
          </p>
        </div>
      </motion.div>
    </div>
  );
}
