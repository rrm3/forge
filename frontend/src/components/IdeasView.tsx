/**
 * IdeasView - Personal "Ideas to Explore" list view.
 *
 * Shows the user's saved ideas with inline editing, delete,
 * and the ability to start a chat linked to an idea.
 */

import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, MessageCircle, MoreVertical, Pencil, Trash2, X, Check, Bold, Italic, List } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { listUserIdeas, updateUserIdea, deleteUserIdea } from '../api/client';
import { useSession } from '../state/SessionContext';
import type { UserIdea } from '../api/types';

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  const diffWeek = Math.floor(diffDay / 7);
  if (diffWeek < 4) return `${diffWeek}w ago`;
  const diffMonth = Math.floor(diffDay / 30);
  return `${diffMonth}mo ago`;
}

function sourceLabel(source: string): string {
  switch (source) {
    case 'brainstorm': return 'Brainstorm';
    case 'intake': return 'Getting Started';
    case 'chat': return 'Chat';
    default: return source || 'Manual';
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'exploring': return 'var(--color-primary)';
    case 'done': return 'var(--color-success, #059669)';
    default: return 'var(--color-text-placeholder)';
  }
}

export function IdeasView() {
  const navigate = useNavigate();
  const { startTypedSession } = useSession();
  const [ideas, setIdeas] = useState<UserIdea[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listUserIdeas();
      // Sort by updated_at desc
      result.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
      setIdeas(result);
    } catch (err) {
      console.error('Failed to fetch ideas:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIdeas();
  }, [fetchIdeas]);

  const handleDelete = useCallback(async (ideaId: string) => {
    try {
      await deleteUserIdea(ideaId);
      setIdeas((prev) => prev.filter((i) => i.idea_id !== ideaId));
    } catch (err) {
      console.error('Failed to delete idea:', err);
    }
    setConfirmDeleteId(null);
    setMenuOpenId(null);
  }, []);

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Header */}
      <div className="px-4 md:px-6 pt-5 pb-4">
        <div className="flex items-center gap-3 mb-2">
          <button
            onClick={() => navigate('/')}
            className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150 hover:bg-[var(--color-surface-raised)]"
            aria-label="Go back"
          >
            <ArrowLeft className="w-5 h-5" style={{ color: 'var(--color-text-secondary)' }} strokeWidth={1.5} />
          </button>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Ideas to Explore
          </h1>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 pb-6">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div
              className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: 'var(--color-primary)' }}
            />
          </div>
        ) : ideas.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              No ideas yet. Start a brainstorm or share what you're curious about.
            </p>
          </div>
        ) : (
          <div className="space-y-3 max-w-2xl mx-auto">
            {ideas.map((idea) => (
              <IdeaCard
                key={idea.idea_id}
                idea={idea}
                isEditing={editingId === idea.idea_id}
                menuOpen={menuOpenId === idea.idea_id}
                confirmDelete={confirmDeleteId === idea.idea_id}
                onStartEdit={() => { setEditingId(idea.idea_id); setMenuOpenId(null); }}
                onCancelEdit={() => setEditingId(null)}
                onSaveEdit={async (fields) => {
                  try {
                    const updated = await updateUserIdea(idea.idea_id, fields);
                    setIdeas((prev) => prev.map((i) => i.idea_id === idea.idea_id ? updated : i));
                    setEditingId(null);
                  } catch (err) {
                    console.error('Failed to update idea:', err);
                  }
                }}
                onToggleMenu={() => setMenuOpenId(menuOpenId === idea.idea_id ? null : idea.idea_id)}
                onCloseMenu={() => setMenuOpenId(null)}
                onRequestDelete={() => { setConfirmDeleteId(idea.idea_id); setMenuOpenId(null); }}
                onConfirmDelete={() => handleDelete(idea.idea_id)}
                onCancelDelete={() => setConfirmDeleteId(null)}
                onChat={() => startTypedSession('chat')}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface IdeaCardProps {
  idea: UserIdea;
  isEditing: boolean;
  menuOpen: boolean;
  confirmDelete: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: (fields: { title?: string; description?: string; tags?: string[]; status?: string }) => void;
  onToggleMenu: () => void;
  onCloseMenu: () => void;
  onRequestDelete: () => void;
  onConfirmDelete: () => void;
  onCancelDelete: () => void;
  onChat: () => void;
}

function IdeaCard({
  idea,
  isEditing,
  menuOpen,
  confirmDelete,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onToggleMenu,
  onCloseMenu,
  onRequestDelete,
  onConfirmDelete,
  onCancelDelete,
  onChat,
}: IdeaCardProps) {
  const [editTitle, setEditTitle] = useState(idea.title);
  const [editDesc, setEditDesc] = useState(idea.description);
  const [editTags, setEditTags] = useState<string[]>(idea.tags);
  const [editStatus, setEditStatus] = useState(idea.status);
  const [tagInput, setTagInput] = useState('');
  const [editMode, setEditMode] = useState<'edit' | 'preview'>('edit');
  const textareaRef = { current: null as HTMLTextAreaElement | null };

  // Reset edit fields when entering edit mode
  useEffect(() => {
    if (isEditing) {
      setEditTitle(idea.title);
      setEditDesc(idea.description);
      setEditTags([...idea.tags]);
      setEditStatus(idea.status);
      setEditMode('edit');
    }
  }, [isEditing, idea]);

  function addTag() {
    const t = tagInput.trim().toLowerCase();
    if (t && !editTags.includes(t)) {
      setEditTags([...editTags, t]);
    }
    setTagInput('');
  }

  if (confirmDelete) {
    return (
      <div
        className="rounded-xl border p-4"
        style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
      >
        <p className="text-sm mb-3" style={{ color: 'var(--color-text-primary)' }}>
          Delete "{idea.title}"?
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={onConfirmDelete}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-colors"
            style={{ backgroundColor: 'var(--color-error, #DC2626)' }}
          >
            <Trash2 className="w-3.5 h-3.5" strokeWidth={2} />
            Delete
          </button>
          <button
            onClick={onCancelDelete}
            className="text-sm font-medium transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (isEditing) {
    return (
      <div
        className="rounded-xl border p-4"
        style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-primary)' }}
      >
        {/* Edit header */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium" style={{ color: 'var(--color-primary)' }}>Editing</span>
          <button
            onClick={() => setEditMode(editMode === 'edit' ? 'preview' : 'edit')}
            className="text-xs font-medium px-2 py-1 rounded-md transition-colors"
            style={{
              color: editMode === 'preview' ? 'var(--color-primary)' : 'var(--color-text-muted)',
              backgroundColor: editMode === 'preview' ? 'var(--color-primary-subtle)' : 'transparent',
            }}
          >
            {editMode === 'edit' ? 'Preview' : 'Edit'}
          </button>
        </div>

        {/* Title */}
        <input
          type="text"
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          className="w-full text-sm font-semibold bg-transparent border-b outline-none pb-1 mb-3"
          style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}
          placeholder="Idea title..."
        />

        {/* Description */}
        {editMode === 'edit' ? (
          <div className="mb-3">
            <div className="flex items-center gap-1 mb-1">
              <button
                onClick={() => {
                  const ta = textareaRef.current;
                  if (!ta) return;
                  const start = ta.selectionStart;
                  const end = ta.selectionEnd;
                  const selected = editDesc.substring(start, end);
                  setEditDesc(editDesc.substring(0, start) + '**' + selected + '**' + editDesc.substring(end));
                }}
                className="p-1 rounded hover:bg-[var(--color-surface-raised)]"
                title="Bold"
              >
                <Bold className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
              </button>
              <button
                onClick={() => {
                  const ta = textareaRef.current;
                  if (!ta) return;
                  const start = ta.selectionStart;
                  const end = ta.selectionEnd;
                  const selected = editDesc.substring(start, end);
                  setEditDesc(editDesc.substring(0, start) + '*' + selected + '*' + editDesc.substring(end));
                }}
                className="p-1 rounded hover:bg-[var(--color-surface-raised)]"
                title="Italic"
              >
                <Italic className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
              </button>
              <button
                onClick={() => {
                  const ta = textareaRef.current;
                  if (!ta) return;
                  const start = ta.selectionStart;
                  const lineStart = editDesc.lastIndexOf('\n', start - 1) + 1;
                  setEditDesc(editDesc.substring(0, lineStart) + '- ' + editDesc.substring(lineStart));
                }}
                className="p-1 rounded hover:bg-[var(--color-surface-raised)]"
                title="List"
              >
                <List className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
              </button>
            </div>
            <textarea
              ref={(el) => { textareaRef.current = el; }}
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
              rows={5}
              className="w-full text-sm bg-transparent border rounded-lg outline-none p-3 resize-y"
              style={{
                color: 'var(--color-text-primary)',
                borderColor: 'var(--color-border)',
                fontFamily: 'inherit',
              }}
              placeholder="Describe your idea..."
            />
          </div>
        ) : (
          <div className="prose prose-sm max-w-none text-sm mb-3" style={{ color: 'var(--color-text-secondary)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{editDesc}</ReactMarkdown>
          </div>
        )}

        {/* Tags */}
        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          {editTags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
              style={{ backgroundColor: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' }}
            >
              {tag}
              <button onClick={() => setEditTags(editTags.filter((t) => t !== tag))}>
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
          <input
            type="text"
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                addTag();
              }
            }}
            onBlur={addTag}
            className="text-xs bg-transparent outline-none w-20"
            style={{ color: 'var(--color-text-muted)' }}
            placeholder="+ tag"
          />
        </div>

        {/* Status */}
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Status:</span>
          <select
            value={editStatus}
            onChange={(e) => setEditStatus(e.target.value)}
            className="text-xs rounded-md border px-2 py-1 outline-none"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
              backgroundColor: 'var(--color-surface-white)',
            }}
          >
            <option value="new">New</option>
            <option value="exploring">Exploring</option>
            <option value="done">Done</option>
          </select>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => onSaveEdit({ title: editTitle, description: editDesc, tags: editTags, status: editStatus })}
            disabled={!editTitle.trim() || !editDesc.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
            style={{ backgroundColor: 'var(--color-primary)' }}
          >
            <Check className="w-3.5 h-3.5" strokeWidth={2} />
            Save
          </button>
          <button
            onClick={onCancelEdit}
            className="text-sm font-medium transition-colors"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // Default: read-only card
  return (
    <div
      className="rounded-xl border p-4 transition-all duration-200 hover:border-[var(--color-primary)]"
      style={{
        backgroundColor: 'var(--color-surface-white)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Top row: source + status + menu */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            From: {sourceLabel(idea.source)}
          </span>
          {idea.linked_sessions.length > 0 && (
            <span className="text-xs" style={{ color: 'var(--color-text-placeholder)' }}>
              {idea.linked_sessions.length} {idea.linked_sessions.length === 1 ? 'chat' : 'chats'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <span
            className="text-xs font-medium"
            style={{ color: statusColor(idea.status) }}
          >
            {idea.status}
          </span>
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleMenu(); }}
              className="p-1 rounded-md transition-colors hover:bg-[var(--color-surface-raised)]"
              aria-label="More options"
            >
              <MoreVertical className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-10" onClick={onCloseMenu} />
                <div
                  className="absolute right-0 top-full mt-1 w-32 rounded-lg border shadow-lg z-20 py-1"
                  style={{
                    backgroundColor: 'var(--color-surface-white)',
                    borderColor: 'var(--color-border)',
                  }}
                >
                  <button
                    onClick={(e) => { e.stopPropagation(); onStartEdit(); }}
                    className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-left transition-colors hover:bg-[var(--color-surface-raised)]"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    <Pencil className="w-3.5 h-3.5" strokeWidth={1.5} />
                    Edit
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); onRequestDelete(); }}
                    className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-left transition-colors hover:bg-[var(--color-surface-raised)]"
                    style={{ color: 'var(--color-error, #DC2626)' }}
                  >
                    <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Title */}
      <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
        {idea.title}
      </p>

      {/* Description (truncated) */}
      <p
        className="text-sm mb-2"
        style={{
          color: 'var(--color-text-secondary)',
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {idea.description}
      </p>

      {/* Tags */}
      {idea.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {idea.tags.map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: 'var(--color-surface-raised)',
                color: 'var(--color-text-muted)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Bottom row: time + chat button */}
      <div className="flex items-center justify-between mt-1">
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {relativeTime(idea.updated_at)}
        </span>
        <button
          onClick={onChat}
          className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm font-medium border transition-colors duration-150"
          style={{
            borderColor: 'var(--color-primary)',
            color: 'var(--color-primary)',
            backgroundColor: 'transparent',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--color-primary-subtle)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          <MessageCircle className="w-3.5 h-3.5" strokeWidth={1.5} />
          Chat
        </button>
      </div>
    </div>
  );
}
