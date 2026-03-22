import { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Lightbulb, Compass, Star, Sunrise, MessageCircle, Search, Plus, ChevronDown, ChevronRight, ClipboardCheck, Home, X } from 'lucide-react';
import { useSession } from '../state/SessionContext';
import type { Session } from '../api/types';

const SESSION_ICONS: Record<string, typeof Lightbulb> = {
  tip: Lightbulb,
  stuck: Compass,
  brainstorm: Star,
  wrapup: Sunrise,
  chat: MessageCircle,
  intake: ClipboardCheck,
};

function getSessionIcon(type: string) {
  return SESSION_ICONS[type] || MessageCircle;
}

function getWeekKey(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();

  // Start of this week (Monday)
  const thisMonday = new Date(now);
  thisMonday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  thisMonday.setHours(0, 0, 0, 0);

  const lastMonday = new Date(thisMonday);
  lastMonday.setDate(thisMonday.getDate() - 7);

  if (date >= thisMonday) return 'This Week';
  if (date >= lastMonday) return 'Last Week';

  // Calculate week number from program start (approximate)
  const weeksAgo = Math.floor((thisMonday.getTime() - date.getTime()) / (7 * 24 * 60 * 60 * 1000));
  return `${weeksAgo + 1} Weeks Ago`;
}

function groupByWeek(sessions: Session[]): [string, Session[]][] {
  const groups = new Map<string, Session[]>();

  const sorted = [...sessions].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  for (const session of sorted) {
    // Don't show incomplete intake sessions
    if (session.type === 'intake' && !session.title) continue;

    const week = getWeekKey(session.updated_at);
    if (!groups.has(week)) groups.set(week, []);
    groups.get(week)!.push(session);
  }

  return Array.from(groups.entries());
}

interface SessionRowProps {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
  canDelete?: boolean;
}

function SessionRow({ session, isActive, onSelect, onDelete, onRename, canDelete = true }: SessionRowProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(session.title || 'New Chat');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  function startEdit() {
    setEditValue(session.title || 'New Chat');
    setEditing(true);
  }

  function commitEdit() {
    setEditing(false);
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== session.title) {
      onRename(trimmed);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') commitEdit();
    if (e.key === 'Escape') setEditing(false);
  }

  function handleDeleteClick(e: React.MouseEvent) {
    e.stopPropagation();
    if (confirmDelete) {
      onDelete();
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 2000);
    }
  }

  const Icon = getSessionIcon(session.type || 'chat');

  return (
    <div
      className={[
        'group flex items-center gap-2 pl-2 pr-2 rounded-lg cursor-pointer select-none',
        isActive
          ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
          : 'hover:bg-[var(--color-surface-raised)]',
      ].join(' ')}
      style={{ height: '36px', minHeight: '36px' }}
      onClick={onSelect}
    >
      <Icon
        className="flex-shrink-0 w-3.5 h-3.5"
        strokeWidth={1.5}
        style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
      />

      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            ref={inputRef}
            className="w-full bg-transparent border-b border-[var(--color-primary)] outline-none text-sm"
            style={{ color: 'var(--color-text-primary)' }}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <p
            className="text-sm truncate"
            style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
            onDoubleClick={(e) => { e.stopPropagation(); startEdit(); }}
          >
            {session.title || 'New Chat'}
          </p>
        )}
      </div>

      {canDelete && (
        <button
          className={[
            'shrink-0 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity',
            confirmDelete ? 'opacity-100 text-red-400' : '',
          ].join(' ')}
          style={{ color: confirmDelete ? undefined : 'var(--color-text-muted)' }}
          onClick={handleDeleteClick}
          title={confirmDelete ? 'Click again to confirm' : 'Delete'}
        >
          {confirmDelete ? (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          )}
        </button>
      )}
    </div>
  );
}

interface SessionListProps {
  ideaCount?: number;
}

export function SessionList({ ideaCount }: SessionListProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, removeSession, updateSessionTitle, startTypedSession } = useSession();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [collapsedWeeks, setCollapsedWeeks] = useState<Set<string>>(new Set());

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return state.sessions;
    const q = searchQuery.toLowerCase();
    return state.sessions.filter(s =>
      (s.title || '').toLowerCase().includes(q)
    );
  }, [state.sessions, searchQuery]);

  const weekGroups = useMemo(() => groupByWeek(filteredSessions), [filteredSessions]);

  function toggleWeek(week: string) {
    setCollapsedWeeks(prev => {
      const next = new Set(prev);
      if (next.has(week)) next.delete(week);
      else next.add(week);
      return next;
    });
  }

  const isHome = location.pathname === '/';
  const showIdeas = location.pathname === '/ideas';

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Home button */}
      <div className="px-2 pt-2">
        <button
          onClick={() => navigate('/')}
          className={[
            'flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors',
            isHome
              ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
              : 'hover:bg-[var(--color-surface-raised)]',
          ].join(' ')}
          style={{ height: '36px', minHeight: '36px' }}
        >
          <Home
            className="flex-shrink-0 w-3.5 h-3.5"
            strokeWidth={1.5}
            style={{ color: isHome ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          />
          <span
            className="text-sm font-medium"
            style={{ color: isHome ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
          >
            Home
          </span>
        </button>
      </div>

      {/* Separator under Home */}
      <div className="mx-3 mt-2 border-b" style={{ borderColor: 'var(--color-border)' }} />

      {/* Ideas button */}
      <div className="px-2 pt-1">
        <button
          onClick={() => navigate('/ideas')}
          className={[
            'flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors',
            showIdeas
              ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
              : 'hover:bg-[var(--color-surface-raised)]',
          ].join(' ')}
          style={{ height: '36px', minHeight: '36px' }}
        >
          <Lightbulb
            className="flex-shrink-0 w-3.5 h-3.5"
            strokeWidth={1.5}
            style={{ color: showIdeas ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          />
          <span
            className="text-sm font-medium flex-1 text-left"
            style={{ color: showIdeas ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
          >
            Ideas
          </span>
          {(ideaCount ?? 0) > 0 && (
            <span className="text-xs" style={{ color: 'var(--color-text-placeholder)' }}>{ideaCount}</span>
          )}
        </button>
      </div>

      {/* Expandable search (shown when search icon clicked) */}
      {searchOpen && (
        <div className="px-3 pt-2">
          <div
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg border"
            style={{
              borderColor: 'var(--color-border)',
              backgroundColor: 'var(--color-surface)',
            }}
          >
            <Search className="w-3.5 h-3.5 flex-shrink-0" style={{ color: 'var(--color-text-placeholder)' }} strokeWidth={1.5} />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-transparent border-none outline-none text-xs"
              style={{ color: 'var(--color-text-primary)' }}
              autoFocus
            />
            <button onClick={() => { setSearchQuery(''); setSearchOpen(false); }}>
              <X className="w-3 h-3" style={{ color: 'var(--color-text-placeholder)' }} />
            </button>
          </div>
        </div>
      )}

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {weekGroups.length === 0 ? (
          <p className="text-xs text-center py-8" style={{ color: 'var(--color-text-placeholder)' }}>
            No conversations yet
          </p>
        ) : (
          weekGroups.map(([week, sessions]) => {
            const isCollapsed = collapsedWeeks.has(week);
            return (
              <div key={week} className="mb-1">
                <button
                  onClick={() => toggleWeek(week)}
                  className="flex items-center gap-1 px-2 py-1.5 w-full text-left rounded-md hover:bg-[var(--color-surface-raised)] transition-colors"
                >
                  {isCollapsed ? (
                    <ChevronRight className="w-3 h-3" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
                  ) : (
                    <ChevronDown className="w-3 h-3" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
                  )}
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                    {week}
                  </span>
                  <span className="text-xs ml-auto" style={{ color: 'var(--color-text-placeholder)' }}>
                    {sessions.length}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="space-y-0.5 mt-0.5">
                    {sessions.map((session) => (
                      <SessionRow
                        key={session.session_id}
                        session={session}
                        isActive={session.session_id === state.activeSessionId}
                        onSelect={() => navigate(`/chat/${session.session_id}`)}
                        onDelete={() => removeSession(session.session_id)}
                        onRename={(title) => updateSessionTitle(session.session_id, title)}
                        canDelete={session.type !== 'intake'}
                      />
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Bottom actions: search + new chat */}
      <div className="flex items-center gap-1 px-3 py-2 border-t" style={{ borderColor: 'var(--color-border)' }}>
        <button
          onClick={() => setSearchOpen(!searchOpen)}
          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
          style={{ color: searchOpen ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          title="Search sessions"
        >
          <Search className="w-4 h-4" strokeWidth={1.5} />
        </button>
        <button
          onClick={() => startTypedSession('chat')}
          className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
          style={{ color: 'var(--color-text-muted)' }}
          title="New chat"
        >
          <Plus className="w-4 h-4" strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
