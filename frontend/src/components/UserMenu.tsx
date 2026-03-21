import { useState, useRef, useEffect } from 'react';
import { LogOut, ChevronUp } from 'lucide-react';
import { useAuth } from '../auth/useAuth';

function getInitials(name: string): string {
  return name
    .split(' ')
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

export function UserMenu() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  if (!user) return null;

  const initials = getInitials(user.name || user.email);

  return (
    <div ref={containerRef} className="relative border-t" style={{ borderColor: 'var(--color-border)' }}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 w-full px-4 py-3 transition-colors hover:bg-[var(--color-surface-raised)]"
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          <span className="text-xs font-semibold text-white">{initials}</span>
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
            {user.name}
          </p>
          <p className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
            {user.email}
          </p>
        </div>
        <ChevronUp
          className={['w-4 h-4 shrink-0 transition-transform', open ? '' : 'rotate-180'].join(' ')}
          style={{ color: 'var(--color-text-placeholder)' }}
          strokeWidth={1.5}
        />
      </button>

      {open && (
        <div
          className="absolute bottom-full left-2 right-2 mb-1 rounded-lg shadow-lg overflow-hidden z-50 border"
          style={{
            backgroundColor: 'var(--color-surface-white)',
            borderColor: 'var(--color-border)',
          }}
        >
          <button
            onClick={() => { setOpen(false); signOut(); }}
            className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm transition-colors hover:bg-[var(--color-surface-raised)]"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <LogOut className="w-4 h-4" strokeWidth={1.5} />
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
