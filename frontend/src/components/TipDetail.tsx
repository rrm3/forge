import { useState, useCallback } from 'react';
import { ArrowLeft, ThumbsUp, Pencil, Trash2, X, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { voteTip, unvoteTip, updateTip, deleteTip } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { ProfileChip } from './ProfileChip';
import { TipCommentSection } from './TipCommentSection';
import type { Tip } from '../api/types';

const DEPARTMENTS = [
  'Everyone',
  'Chief Of Staff', 'Customer Solutions', 'Customer Success',
  'Finance', 'Global', 'Legal', 'Marketing',
  'Operations', 'People', 'Product', 'Sales', 'Technology',
];

interface TipDetailProps {
  tip: Tip;
  onBack: () => void;
  onVoteChange: (tipId: string, voted: boolean, newCount: number) => void;
  onTipUpdated?: (tip: Tip) => void;
  onTipDeleted?: (tipId: string) => void;
}

function formatDepartmentName(slug: string): string {
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
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

export function TipDetail({ tip, onBack, onVoteChange, onTipUpdated, onTipDeleted }: TipDetailProps) {
  const { user } = useAuth();
  const isAuthor = user?.userId === tip.author_id;

  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(tip.title);
  const [editContent, setEditContent] = useState(tip.content);
  const [editTags, setEditTags] = useState<string[]>(tip.tags);
  const [editDepartment, setEditDepartment] = useState(tip.department);
  const [tagInput, setTagInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function startEditing() {
    setEditTitle(tip.title);
    setEditContent(tip.content);
    setEditTags([...tip.tags]);
    setEditDepartment(tip.department);
    setEditing(true);
    setError(null);
  }

  function cancelEditing() {
    setEditing(false);
    setError(null);
  }

  function addTag() {
    const t = tagInput.trim().toLowerCase();
    if (t && !editTags.includes(t)) {
      setEditTags([...editTags, t]);
    }
    setTagInput('');
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateTip(tip.tip_id, {
        title: editTitle,
        content: editContent,
        tags: editTags,
        department: editDepartment,
      });
      onTipUpdated?.(updated);
      setEditing(false);
    } catch (err) {
      console.error('Failed to update tip:', err);
      setError('Failed to save changes.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteTip(tip.tip_id);
      onTipDeleted?.(tip.tip_id);
    } catch (err) {
      console.error('Failed to delete tip:', err);
      setError('Failed to delete tip.');
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  const handleVote = useCallback(async () => {
    const wasVoted = tip.user_has_voted;
    const newCount = wasVoted ? tip.vote_count - 1 : tip.vote_count + 1;
    onVoteChange(tip.tip_id, !wasVoted, newCount);
    try {
      if (wasVoted) {
        await unvoteTip(tip.tip_id);
      } else {
        await voteTip(tip.tip_id);
      }
    } catch {
      onVoteChange(tip.tip_id, wasVoted, tip.vote_count);
    }
  }, [tip, onVoteChange]);

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-5">
        <div className="max-w-2xl mx-auto">
          {/* Back link */}
          <button
            onClick={onBack}
            className="flex items-center gap-2 mb-5 transition-colors duration-150 hover:opacity-70"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
            <span className="text-sm font-medium">Back to Tips</span>
          </button>

          {editing ? (
            /* ---- Edit mode ---- */
            <div className="space-y-4">
              {/* Title */}
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full text-2xl font-semibold bg-transparent border-b outline-none pb-2"
                style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}
                placeholder="Tip title..."
              />

              {/* Content */}
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={10}
                className="w-full text-sm bg-transparent border rounded-lg outline-none p-3 resize-y"
                style={{
                  color: 'var(--color-text-primary)',
                  borderColor: 'var(--color-border)',
                  fontFamily: 'inherit',
                }}
                placeholder="Write your tip in markdown..."
              />

              {/* Tags */}
              <div className="flex flex-wrap items-center gap-1.5">
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

              {/* Department */}
              <div className="flex items-center gap-2">
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Share with:</span>
                <select
                  value={editDepartment}
                  onChange={(e) => setEditDepartment(e.target.value)}
                  className="text-xs rounded-md border px-2 py-1 outline-none"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                    backgroundColor: 'var(--color-surface-white)',
                  }}
                >
                  {DEPARTMENTS.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              {error && (
                <p className="text-xs" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
              )}

              {/* Save / Cancel buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSave}
                  disabled={saving || !editTitle.trim() || !editContent.trim()}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                >
                  {saving ? (
                    <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
                  ) : (
                    <Check className="w-4 h-4" strokeWidth={2} />
                  )}
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={cancelEditing}
                  disabled={saving}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            /* ---- View mode ---- */
            <>
              {/* Title + action buttons */}
              <div className="flex items-start justify-between gap-3 mb-3">
                <h1 className="text-2xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {tip.title}
                </h1>
                {isAuthor && (
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={startEditing}
                      className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
                      title="Edit tip"
                      aria-label="Edit tip"
                    >
                      <Pencil className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
                    </button>
                    {confirmDelete ? (
                      <div className="flex items-center gap-1 ml-1">
                        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Delete?</span>
                        <button
                          onClick={handleDelete}
                          disabled={deleting}
                          className="text-xs font-medium px-2 py-1 rounded-md"
                          style={{ color: '#DC2626', backgroundColor: '#FEE2E2' }}
                        >
                          {deleting ? '...' : 'Yes'}
                        </button>
                        <button
                          onClick={() => setConfirmDelete(false)}
                          disabled={deleting}
                          className="text-xs font-medium px-2 py-1 rounded-md"
                          style={{ color: 'var(--color-text-secondary)' }}
                        >
                          No
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDelete(true)}
                        className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
                        title="Delete tip"
                        aria-label="Delete tip"
                      >
                        <Trash2 className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Author, department, date */}
              <div className="flex flex-wrap items-center gap-2 mb-5">
                <ProfileChip userId={tip.author_id} avatarSize={24} />
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: 'var(--color-surface-raised)',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  {formatDepartmentName(tip.department)}
                </span>
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {relativeTime(tip.created_at)}
                </span>
              </div>

              {/* Content as markdown */}
              <div
                className="prose prose-sm max-w-none mb-5"
                style={{ color: 'var(--color-text-primary)' }}
              >
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {tip.content}
                </ReactMarkdown>
              </div>

              {/* Tags */}
              {tip.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-5">
                  {tip.tags.map((tag) => (
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

              {error && (
                <p className="text-xs mb-3" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
              )}

              {/* Upvote button */}
              <button
                onClick={handleVote}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors duration-150"
                style={{
                  backgroundColor: tip.user_has_voted ? 'var(--color-primary-subtle)' : 'var(--color-surface-white)',
                  borderColor: tip.user_has_voted ? 'var(--color-primary)' : 'var(--color-border)',
                  color: tip.user_has_voted ? 'var(--color-primary)' : 'var(--color-text-muted)',
                }}
                aria-label={tip.user_has_voted ? 'Remove upvote' : 'Upvote'}
              >
                <ThumbsUp
                  className="w-4 h-4"
                  strokeWidth={1.5}
                  fill={tip.user_has_voted ? 'currentColor' : 'none'}
                />
                <span className="text-sm font-medium">{tip.vote_count}</span>
              </button>

              {/* Discussion thread */}
              <TipCommentSection tipId={tip.tip_id} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
