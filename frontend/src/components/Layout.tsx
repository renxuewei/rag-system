import { ReactNode } from 'react';
import { Page } from '../App';
import { Moon, Sun, LogOut, Database, MessageSquare, ShieldAlert } from 'lucide-react';
import { cn } from '../lib/utils';

interface LayoutProps {
  children: ReactNode;
  currentPage: Page;
  onNavigate: (page: Page) => void;
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

export default function Layout({ children, currentPage, onNavigate, theme, toggleTheme }: LayoutProps) {
  const navItems = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'documents', label: 'Documents', icon: Database },
    { id: 'admin', label: 'Admin', icon: ShieldAlert },
  ];

  return (
    <div className="h-full w-full flex flex-col bg-[var(--color-bg)] text-[var(--color-text-main)] transition-colors duration-200 overflow-hidden">
      <nav className="h-[60px] flex-shrink-0 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex items-center justify-between px-6 z-10 transition-colors duration-200">
        <div className="flex items-center gap-8">
          <h1 className="text-lg font-semibold text-[var(--color-text-main)]">RAG Knowledge Base</h1>
          
          <div className="hidden md:flex items-center gap-1">
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id as Page)}
                className={cn(
                  "px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2",
                  currentPage === item.id 
                    ? "bg-[var(--color-primary)]/10 text-[var(--color-primary)]" 
                    : "text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text-main)]"
                )}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button 
            onClick={toggleTheme}
            className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-[var(--color-bg)] transition-colors text-[var(--color-text-sec)]"
            aria-label="Toggle theme"
          >
            {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          </button>
          
          <button 
            onClick={() => {
              localStorage.removeItem('token');
              onNavigate('login');
            }}
            className="h-8 px-4 rounded-md border border-[var(--color-border)] text-sm font-medium text-[var(--color-text-sec)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text-main)] transition-colors flex items-center gap-2"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </nav>

      <main className="flex-1 flex overflow-hidden">
        {children}
      </main>
    </div>
  );
}
