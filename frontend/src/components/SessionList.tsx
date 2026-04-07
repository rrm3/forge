import { useState, useRef, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { Lightbulb, Compass, Star, Sunrise, MessageCircle, Search, Plus, ChevronDown, ChevronRight, ClipboardCheck, ClipboardList, Home, X, BookOpen, Users, ExternalLink } from 'lucide-react';
import Tooltip from '@mui/material/Tooltip';
import { useSession } from '../state/SessionContext';
import { resetIntake } from '../api/client';
import { ConfirmResetModal } from './ConfirmResetModal';
import { PROGRAM_START_DATE } from '../program';
import type { Session } from '../api/types';

const SESSION_ICONS: Record<string, typeof Lightbulb> = {
  tip: Lightbulb,
  stuck: Compass,
  brainstorm: Star,
  wrapup: Sunrise,
  chat: MessageCircle,
  intake: ClipboardCheck,
  collab: Users,
};

// Session types that get visual emphasis (accent bar + always-colored icon)
const FEATURED_SESSION_TYPES = new Set(['intake', 'wrapup']);

function getSessionIcon(type: string) {
  return SESSION_ICONS[type] || MessageCircle;
}

/** Get the Tuesday date for a given program week label like "Week 1". */
function getTuesdayForWeek(weekLabel: string): string {
  const match = weekLabel.match(/^Week (\d+)$/);
  if (!match) return '';
  const weekNum = parseInt(match[1], 10);
  // PROGRAM_START_DATE is a Tuesday (2026-03-24). Offset by +7 per additional week.
  const tuesday = new Date(PROGRAM_START_DATE);
  tuesday.setDate(tuesday.getDate() + (weekNum - 1) * 7);
  return tuesday.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
}

function groupByWeek(sessions: Session[]): [string, Session[]][] {
  const groups = new Map<string, Session[]>();

  const sorted = [...sessions].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  for (const session of sorted) {
    // Don't show incomplete intake sessions
    if (session.type === 'intake' && !session.title) continue;

    const week = `Week ${session.program_week || 1}`;
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
  immediateDelete?: boolean;  // skip inline "Delete?" confirm (e.g. intake uses a modal instead)
}

const SESSION_DEFAULT_TITLES: Record<string, string> = {
  tip: 'New Tip',
  collab: 'New Collab',
  stuck: 'Get Help',
  brainstorm: 'New Brainstorm',
  wrapup: 'Wrap-up',
  chat: 'New Chat',
};

function getDefaultTitle(session: Session): string {
  return session.title || SESSION_DEFAULT_TITLES[session.type] || 'New Chat';
}

function SessionRow({ session, isActive, onSelect, onDelete, onRename, canDelete = true, immediateDelete }: SessionRowProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(getDefaultTitle(session));
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  function startEdit() {
    setEditValue(getDefaultTitle(session));
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
    if (immediateDelete) {
      onDelete();
      return;
    }
    if (confirmDelete) {
      onDelete();
      setConfirmDelete(false);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000);
    }
  }

  const Icon = getSessionIcon(session.type || 'chat');
  const isFeatured = FEATURED_SESSION_TYPES.has(session.type || 'chat');

  return (
    <div
      className={[
        'group flex items-center gap-2 px-2 rounded-lg cursor-pointer select-none',
        isActive
          ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
          : 'hover:bg-[var(--color-surface-raised)]',
      ].join(' ')}
      style={{
        height: '36px',
        minHeight: '36px',
      }}
      onClick={onSelect}
    >
      <Icon
        className="flex-shrink-0 w-3.5 h-3.5"
        style={{
          color: isActive ? 'var(--color-primary)' : isFeatured ? '#8B5CF6' : 'var(--color-text-muted)',
        }}
        strokeWidth={1.5}
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
            style={{ color: isActive ? 'var(--color-primary)' : isFeatured ? '#8B5CF6' : 'var(--color-text-secondary)' }}
            onDoubleClick={(e) => { e.stopPropagation(); startEdit(); }}
          >
            {getDefaultTitle(session)}
          </p>
        )}
      </div>

      {canDelete && (
        confirmDelete ? (
          <button
            className="shrink-0 px-1.5 py-0.5 rounded text-xs font-medium text-red-500 bg-red-50 hover:bg-red-100 transition-colors"
            onClick={handleDeleteClick}
          >
            Delete?
          </button>
        ) : (
          <button
            className="shrink-0 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity"
            style={{ color: 'var(--color-text-muted)' }}
            onClick={handleDeleteClick}
            title="Delete"
          >
            <X className="w-3.5 h-3.5" strokeWidth={2} />
          </button>
        )
      )}
    </div>
  );
}

interface SessionListProps {
  ideaCount?: number;
  hasTeam?: boolean;
}

export function SessionList({ ideaCount, hasTeam }: SessionListProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, removeSession, updateSessionTitle, startTypedSession } = useSession();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [collapsedWeeks, setCollapsedWeeks] = useState<Set<string>>(new Set());
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);

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
  const showTips = location.pathname.startsWith('/tips');
  const showCollabs = location.pathname.startsWith('/collabs');
  const showActivity = location.pathname === '/activity';
  const showTeam = location.pathname === '/team';

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
            Ideas to Explore
          </span>
          {(ideaCount ?? 0) > 0 && (
            <span className="text-xs" style={{ color: 'var(--color-text-placeholder)' }}>{ideaCount}</span>
          )}
        </button>
      </div>

      {/* Tips & Tricks button */}
      <div className="px-2">
        <button
          onClick={() => navigate('/tips')}
          className={[
            'flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors',
            showTips
              ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
              : 'hover:bg-[var(--color-surface-raised)]',
          ].join(' ')}
          style={{ height: '36px', minHeight: '36px' }}
        >
          <BookOpen
            className="flex-shrink-0 w-3.5 h-3.5"
            strokeWidth={1.5}
            style={{ color: showTips ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          />
          <span
            className="text-sm font-medium"
            style={{ color: showTips ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
          >
            Tips & Tricks
          </span>
        </button>
      </div>

      {/* Collabs button */}
      <div className="px-2">
        <button
          onClick={() => navigate('/collabs')}
          className={[
            'flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors',
            showCollabs
              ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
              : 'hover:bg-[var(--color-surface-raised)]',
          ].join(' ')}
          style={{ height: '36px', minHeight: '36px' }}
        >
          <Users
            className="flex-shrink-0 w-3.5 h-3.5"
            strokeWidth={1.5}
            style={{ color: showCollabs ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          />
          <span
            className="text-sm font-medium"
            style={{ color: showCollabs ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
          >
            Collabs
          </span>
        </button>
      </div>

      {/* Activity Log - visible to everyone */}
      <div className="px-2">
        <button
          onClick={() => navigate('/activity')}
          className={[
            'flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors',
            showActivity
              ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
              : 'hover:bg-[var(--color-surface-raised)]',
          ].join(' ')}
          style={{ height: '36px', minHeight: '36px' }}
        >
          <ClipboardList
            className="flex-shrink-0 w-3.5 h-3.5"
            strokeWidth={1.5}
            style={{ color: showActivity ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
          />
          <span
            className="text-sm font-medium"
            style={{ color: showActivity ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
          >
            Activity Log
          </span>
        </button>
      </div>

      {/* My Team - visible to managers only */}
      {hasTeam && (
        <div className="px-2">
          <button
            onClick={() => navigate('/team')}
            className={[
              'flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors',
              showTeam
                ? 'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]'
                : 'hover:bg-[var(--color-surface-raised)]',
            ].join(' ')}
            style={{ height: '36px', minHeight: '36px' }}
          >
            <Users
              className="flex-shrink-0 w-3.5 h-3.5"
              strokeWidth={1.5}
              style={{ color: showTeam ? 'var(--color-primary)' : 'var(--color-text-muted)' }}
            />
            <span
              className="text-sm font-medium"
              style={{ color: showTeam ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}
            >
              My Team
            </span>
          </button>
        </div>
      )}

      {/* AI Tuesdays on Guru - external link */}
      <div className="px-2">
        <a
          href="https://app.getguru.com/page/31fe984d-f863-4487-8080-849d9f3461ef"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 w-full pl-2 pr-2 rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
          style={{ height: '36px', minHeight: '36px', textDecoration: 'none' }}
        >
          <ExternalLink
            className="flex-shrink-0 w-3.5 h-3.5"
            strokeWidth={1.5}
            style={{ color: 'var(--color-text-muted)' }}
          />
          <span
            className="text-sm font-medium flex-1"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            AI Tuesdays on Guru
          </span>
        </a>
      </div>

      {/* Separator under nav items */}
      <div className="mx-3 mt-1 mb-1 border-b" style={{ borderColor: 'var(--color-border)' }} />

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
            const tuesdayDate = getTuesdayForWeek(week);
            return (
              <div key={week} className="mb-1">
                <Tooltip title={tuesdayDate || week} placement="right" arrow>
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
                </Tooltip>

                {!isCollapsed && (
                  <div className="space-y-0.5 mt-0.5">
                    {sessions.map((session) => (
                      <SessionRow
                        key={session.session_id}
                        session={session}
                        isActive={session.session_id === state.activeSessionId}
                        onSelect={() => navigate(`/chat/${session.session_id}`)}
                        onDelete={session.type === 'intake'
                          ? () => { setResetModalOpen(true); }
                          : async () => {
                              try {
                                const wasActive = session.session_id === state.activeSessionId;
                                await removeSession(session.session_id);
                                if (wasActive) navigate('/');
                              } catch (err) {
                                console.error('Failed to delete session:', err);
                              }
                            }
                        }
                        onRename={(title) => updateSessionTitle(session.session_id, title)}
                        canDelete
                        immediateDelete={session.type === 'intake'}
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

      {createPortal(
        <ConfirmResetModal
          open={resetModalOpen}
          onCancel={() => setResetModalOpen(false)}
          onConfirm={async () => {
            setResetLoading(true);
            try {
              await resetIntake();
              window.location.href = '/day1';
            } catch (err) {
              console.error('Failed to reset intake:', err);
              setResetLoading(false);
              setResetModalOpen(false);
            }
          }}
          loading={resetLoading}
        />,
        document.body
      )}
    </div>
  );
}
