import { useState, type ReactNode } from 'react';
import { Menu } from 'lucide-react';

interface AppShellProps {
  sidebar: ReactNode;
  content: ReactNode;
}

export function AppShell({ sidebar, content }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-full overflow-hidden" style={{ backgroundColor: 'var(--color-surface)' }}>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/30 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={[
          'fixed inset-y-0 left-0 z-30 w-72 border-r flex flex-col',
          'transition-transform duration-200 ease-in-out',
          'md:static md:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
        style={{
          backgroundColor: 'var(--color-surface-white)',
          borderColor: 'var(--color-border)',
        }}
      >
        {sidebar}
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Mobile header */}
        <div
          className="flex items-center h-11 px-4 border-b md:hidden"
          style={{
            backgroundColor: 'var(--color-surface-white)',
            borderColor: 'var(--color-border)',
          }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
            aria-label="Open sidebar"
          >
            <Menu className="w-5 h-5" strokeWidth={1.5} />
          </button>
          <span className="ml-3 text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            AI Tuesdays
          </span>
        </div>

        <div className="flex-1 overflow-hidden">
          {content}
        </div>
      </div>
    </div>
  );
}
