import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Send, Pencil, Trash2, Check, X } from 'lucide-react';
import { listTipComments, addTipComment, updateTipComment, deleteTipComment } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { ProfileChip } from './ProfileChip';
import type { TipComment } from '../api/types';

interface TipCommentSectionProps {
  tipId: string;
}

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

export function TipCommentSection({ tipId }: TipCommentSectionProps) {
  const { user } = useAuth();
  const [comments, setComments] = useState<TipComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  // Delete confirmation state
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deleteInProgress, setDeleteInProgress] = useState(false);

  const fetchComments = useCallback(async () => {
    try {
      const data = await listTipComments(tipId);
      setComments(data);
    } catch {
      // silently fail on load - empty state is fine
    } finally {
      setLoading(false);
    }
  }, [tipId]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || submitting || !user) return;

    setSubmitting(true);
    setError(null);
    try {
      const newComment = await addTipComment(tipId, trimmed);
      setComments((prev) => [...prev, newComment]);
      setContent('');
    } catch {
      setError('Failed to post comment.');
    } finally {
      setSubmitting(false);
    }
  }

  function startEditing(comment: TipComment) {
    setEditingId(comment.comment_id);
    setEditContent(comment.content);
    setConfirmDeleteId(null);
    setError(null);
  }

  function cancelEditing() {
    setEditingId(null);
    setEditContent('');
  }

  async function handleEditSave(commentId: string) {
    const trimmed = editContent.trim();
    if (!trimmed || editSaving) return;

    setEditSaving(true);
    setError(null);
    try {
      const updated = await updateTipComment(tipId, commentId, trimmed);
      setComments((prev) => prev.map((c) => (c.comment_id === commentId ? updated : c)));
      setEditingId(null);
      setEditContent('');
    } catch {
      setError('Failed to save edit.');
    } finally {
      setEditSaving(false);
    }
  }

  async function handleDelete(commentId: string) {
    setDeleteInProgress(true);
    setError(null);
    try {
      await deleteTipComment(tipId, commentId);
      setComments((prev) => prev.filter((c) => c.comment_id !== commentId));
      setConfirmDeleteId(null);
    } catch {
      setError('Failed to delete comment.');
    } finally {
      setDeleteInProgress(false);
    }
  }

  const isOwn = (authorId: string) => user?.userId === authorId;

  return (
    <div className="mt-6 pt-6" style={{ borderTop: '1px solid var(--color-border)' }}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
        <span className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
          {loading ? 'Comments' : `${comments.length} Comment${comments.length !== 1 ? 's' : ''}`}
        </span>
      </div>

      {/* Comment list */}
      {comments.length > 0 && (
        <div className="space-y-4 mb-5">
          {comments.map((comment) => (
            <div key={comment.comment_id}>
              <div className="flex items-center gap-2 mb-1">
                <ProfileChip userId={comment.author_id} avatarSize={24} />
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {relativeTime(comment.created_at)}
                </span>

                {/* Edit/delete actions for own comments */}
                {isOwn(comment.author_id) && editingId !== comment.comment_id && (
                  <div className="flex items-center gap-0.5 ml-auto">
                    <button
                      onClick={() => startEditing(comment)}
                      className="flex items-center justify-center w-6 h-6 rounded transition-colors hover:bg-[var(--color-surface-raised)]"
                      title="Edit comment"
                      aria-label="Edit comment"
                    >
                      <Pencil className="w-3 h-3" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
                    </button>
                    {confirmDeleteId === comment.comment_id ? (
                      <div className="flex items-center gap-1 ml-1">
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Delete?</span>
                        <button
                          onClick={() => handleDelete(comment.comment_id)}
                          disabled={deleteInProgress}
                          className="text-xs font-medium px-1.5 py-0.5 rounded"
                          style={{ color: '#DC2626', backgroundColor: '#FEE2E2' }}
                        >
                          {deleteInProgress ? '...' : 'Yes'}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          disabled={deleteInProgress}
                          className="text-xs font-medium px-1.5 py-0.5 rounded"
                          style={{ color: 'var(--color-text-secondary)' }}
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setConfirmDeleteId(comment.comment_id); setEditingId(null); }}
                        className="flex items-center justify-center w-6 h-6 rounded transition-colors hover:bg-[var(--color-surface-raised)]"
                        title="Delete comment"
                        aria-label="Delete comment"
                      >
                        <Trash2 className="w-3 h-3" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Editing mode */}
              {editingId === comment.comment_id ? (
                <div className="pl-[30px]">
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault();
                        handleEditSave(comment.comment_id);
                      }
                      if (e.key === 'Escape') cancelEditing();
                    }}
                    rows={2}
                    className="w-full text-sm bg-transparent border rounded-lg outline-none p-2 resize-none"
                    style={{
                      color: 'var(--color-text-primary)',
                      borderColor: 'var(--color-primary)',
                      fontFamily: 'inherit',
                    }}
                    disabled={editSaving}
                    autoFocus
                  />
                  <div className="flex items-center gap-1.5 mt-1.5">
                    <button
                      onClick={() => handleEditSave(comment.comment_id)}
                      disabled={editSaving || !editContent.trim()}
                      className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md text-white transition-colors disabled:opacity-50"
                      style={{ backgroundColor: 'var(--color-primary)' }}
                    >
                      {editSaving ? (
                        <div className="w-3 h-3 border-2 border-t-transparent border-white rounded-full animate-spin" />
                      ) : (
                        <Check className="w-3 h-3" strokeWidth={2} />
                      )}
                      Save
                    </button>
                    <button
                      onClick={cancelEditing}
                      disabled={editSaving}
                      className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md transition-colors"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      <X className="w-3 h-3" strokeWidth={2} />
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap pl-[30px]" style={{ color: 'var(--color-text-primary)' }}>
                  {comment.content}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && comments.length === 0 && (
        <p className="text-xs mb-4" style={{ color: 'var(--color-text-muted)' }}>
          No comments yet. Start the discussion.
        </p>
      )}

      {/* Comment input */}
      {user && (
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder="Add a comment..."
            rows={2}
            className="flex-1 text-sm bg-transparent border rounded-lg outline-none p-3 resize-none transition-colors duration-100"
            style={{
              color: 'var(--color-text-primary)',
              borderColor: 'var(--color-border)',
              fontFamily: 'inherit',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-primary)';
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-border)';
            }}
            disabled={submitting}
          />
          <button
            type="submit"
            disabled={submitting || !content.trim()}
            className="self-end flex items-center justify-center w-9 h-9 rounded-lg transition-colors duration-100 disabled:opacity-40"
            style={{ backgroundColor: 'var(--color-primary)', color: '#fff' }}
            title="Post comment (⌘+Enter)"
            aria-label="Post comment"
          >
            {submitting ? (
              <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
            ) : (
              <Send className="w-4 h-4" strokeWidth={1.5} />
            )}
          </button>
        </form>
      )}

      {error && (
        <p className="text-xs mt-2" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
      )}
    </div>
  );
}
