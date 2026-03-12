import { useState, useRef, useEffect } from 'react';
import { useSession } from '../state/SessionContext';
import type { Session } from '../api/types';

function formatDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMs / 3600000);
  const diffDay = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay === 1) return 'yesterday';
  if (diffDay < 7) return `${diffDay} days ago`;

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

interface SessionRowProps {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}

function SessionRow({ session, isActive, onSelect, onDelete, onRename }: SessionRowProps) {
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

  return (
    <div
      className={[
        'group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer select-none',
        isActive
          ? 'bg-blue-600 text-white'
          : 'text-gray-300 hover:bg-gray-700',
      ].join(' ')}
      onClick={onSelect}
    >
      <div className="flex-1 min-w-0">
        {editing ? (
          <input
            ref={inputRef}
            className="w-full bg-transparent border-b border-white/50 outline-none text-sm text-white"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <p
            className="text-sm font-medium truncate"
            onDoubleClick={(e) => { e.stopPropagation(); startEdit(); }}
          >
            {session.title || 'New Chat'}
          </p>
        )}
        <p className={['text-xs mt-0.5', isActive ? 'text-blue-200' : 'text-gray-500'].join(' ')}>
          {formatDate(session.updated_at)}
        </p>
      </div>

      <button
        className={[
          'shrink-0 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity',
          isActive
            ? 'hover:bg-blue-500 text-blue-200 hover:text-white'
            : 'hover:bg-gray-600 text-gray-500 hover:text-gray-200',
          confirmDelete ? 'opacity-100 text-red-400' : '',
        ].join(' ')}
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
    </div>
  );
}

export function SessionList() {
  const { state, selectSession, newSession, removeSession, updateSessionTitle } = useSession();

  const sorted = [...state.sessions].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  async function handleNew() {
    await newSession();
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-gray-700/50">
        <h1 className="text-sm font-semibold text-white tracking-wide">AI Tuesdays</h1>
        <button
          onClick={handleNew}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs font-medium transition-colors"
          title="New Chat"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {sorted.length === 0 ? (
          <p className="text-xs text-gray-500 text-center mt-8 px-4">
            No conversations yet. Start a new chat to begin.
          </p>
        ) : (
          sorted.map((session) => (
            <SessionRow
              key={session.session_id}
              session={session}
              isActive={session.session_id === state.activeSessionId}
              onSelect={() => selectSession(session.session_id)}
              onDelete={() => removeSession(session.session_id)}
              onRename={(title) => updateSessionTitle(session.session_id, title)}
            />
          ))
        )}
      </div>
    </div>
  );
}
