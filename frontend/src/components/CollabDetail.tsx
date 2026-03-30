import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Pencil, Trash2, Check, X, Send, MessageSquare, HandHeart } from 'lucide-react';
import { useAuth } from '../auth/useAuth';
import { ProfileChip } from './ProfileChip';
import {
  expressInterest,
  withdrawInterest,
  updateCollab,
  deleteCollab,
  updateCollabStatus,
  listCollabComments,
  addCollabComment,
  deleteCollabComment,
} from '../api/client';
import type { Collaboration, CollabStatus, CollabComment } from '../api/types';

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

function StatusBadge({ status }: { status: CollabStatus }) {
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  let style: React.CSSProperties = {};

  switch (status) {
    case 'open':
      style = { backgroundColor: '#ECFDF5', color: '#059669' };
      break;
    case 'building':
      style = { backgroundColor: 'var(--color-primary-subtle)', color: 'var(--color-primary)' };
      break;
    case 'done':
      style = { backgroundColor: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' };
      break;
    case 'archived':
      style = { backgroundColor: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' };
      break;
  }

  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={style}>
      {label}
    </span>
  );
}

const STATUS_OPTIONS: { value: CollabStatus; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'building', label: 'Building' },
  { value: 'done', label: 'Done' },
];

interface CollabDetailProps {
  collab: Collaboration;
  onBack: () => void;
  onCollabUpdated?: (collab: Collaboration) => void;
  onCollabDeleted?: () => void;
}

export function CollabDetail({ collab, onBack, onCollabUpdated, onCollabDeleted }: CollabDetailProps) {
  const { user } = useAuth();
  const isAuthor = user?.userId === collab.author_id;

  // Interest state
  const [interested, setInterested] = useState(collab.user_has_interest);
  const [interestedIds, setInterestedIds] = useState<string[]>(collab.interested_ids);
  const [interestLoading, setInterestLoading] = useState(false);

  // Edit state
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(collab.title);
  const [editProblem, setEditProblem] = useState(collab.problem);
  const [editSkills, setEditSkills] = useState<string[]>(collab.needed_skills);
  const [editTimeCommitment, setEditTimeCommitment] = useState(collab.time_commitment);
  const [skillInput, setSkillInput] = useState('');
  const [saving, setSaving] = useState(false);

  // Delete state
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Status change
  const [statusLoading, setStatusLoading] = useState(false);

  // Comments
  const [comments, setComments] = useState<CollabComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(true);
  const [commentContent, setCommentContent] = useState('');
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [confirmDeleteCommentId, setConfirmDeleteCommentId] = useState<string | null>(null);
  const [deleteCommentInProgress, setDeleteCommentInProgress] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // Sync from props if collab changes
  useEffect(() => {
    setInterested(collab.user_has_interest);
    setInterestedIds(collab.interested_ids);
  }, [collab.user_has_interest, collab.interested_ids]);

  // Load comments
  const fetchComments = useCallback(async () => {
    try {
      const data = await listCollabComments(collab.collab_id);
      setComments(data);
    } catch {
      // silently fail
    } finally {
      setCommentsLoading(false);
    }
  }, [collab.collab_id]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  async function handleInterestToggle() {
    if (interestLoading || !user) return;
    setInterestLoading(true);
    const wasInterested = interested;

    // Optimistic update
    setInterested(!wasInterested);
    if (wasInterested) {
      setInterestedIds((prev) => prev.filter((id) => id !== user.userId));
    } else {
      setInterestedIds((prev) => [...prev, user.userId]);
    }

    try {
      if (wasInterested) {
        await withdrawInterest(collab.collab_id);
      } else {
        await expressInterest(collab.collab_id);
      }
    } catch {
      // Revert
      setInterested(wasInterested);
      setInterestedIds(collab.interested_ids);
    } finally {
      setInterestLoading(false);
    }
  }

  async function handleStatusChange(newStatus: CollabStatus) {
    setStatusLoading(true);
    setError(null);
    try {
      const updated = await updateCollabStatus(collab.collab_id, newStatus);
      onCollabUpdated?.(updated);
    } catch {
      setError('Failed to update status.');
    } finally {
      setStatusLoading(false);
    }
  }

  function startEditing() {
    setEditTitle(collab.title);
    setEditProblem(collab.problem);
    setEditSkills([...collab.needed_skills]);
    setEditTimeCommitment(collab.time_commitment);
    setEditing(true);
    setError(null);
  }

  function addSkill() {
    const s = skillInput.trim();
    if (s && !editSkills.includes(s)) {
      setEditSkills([...editSkills, s]);
    }
    setSkillInput('');
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateCollab(collab.collab_id, {
        title: editTitle,
        problem: editProblem,
        needed_skills: editSkills,
        time_commitment: editTimeCommitment,
      });
      onCollabUpdated?.(updated);
      setEditing(false);
    } catch {
      setError('Failed to save changes.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteCollab(collab.collab_id);
      onCollabDeleted?.();
    } catch {
      setError('Failed to delete collab.');
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleCommentSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = commentContent.trim();
    if (!trimmed || commentSubmitting || !user) return;

    setCommentSubmitting(true);
    setError(null);
    try {
      const newComment = await addCollabComment(collab.collab_id, trimmed);
      setComments((prev) => [...prev, newComment]);
      setCommentContent('');
    } catch {
      setError('Failed to post comment.');
    } finally {
      setCommentSubmitting(false);
    }
  }

  async function handleDeleteComment(commentId: string) {
    setDeleteCommentInProgress(true);
    setError(null);
    try {
      await deleteCollabComment(collab.collab_id, commentId);
      setComments((prev) => prev.filter((c) => c.comment_id !== commentId));
      setConfirmDeleteCommentId(null);
    } catch {
      setError('Failed to delete comment.');
    } finally {
      setDeleteCommentInProgress(false);
    }
  }

  const isOwnComment = (authorId: string) => user?.userId === authorId;

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
            <span className="text-sm font-medium">Back to Collabs</span>
          </button>

          {editing ? (
            /* ---- Edit mode ---- */
            <div className="space-y-4">
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full text-2xl font-semibold bg-transparent border-b outline-none pb-2"
                style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}
                placeholder="Title..."
              />

              <textarea
                value={editProblem}
                onChange={(e) => setEditProblem(e.target.value)}
                rows={6}
                className="w-full text-sm bg-transparent border rounded-lg outline-none p-3 resize-y"
                style={{
                  color: 'var(--color-text-primary)',
                  borderColor: 'var(--color-border)',
                  fontFamily: 'inherit',
                }}
                placeholder="What problem are you trying to solve?"
              />

              {/* Skills editor */}
              <div>
                <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                  Needed Skills
                </label>
                <div className="flex flex-wrap items-center gap-1.5">
                  {editSkills.map((skill) => (
                    <span
                      key={skill}
                      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                      style={{ border: '1px solid var(--color-primary)', color: 'var(--color-primary)' }}
                    >
                      {skill}
                      <button onClick={() => setEditSkills(editSkills.filter((s) => s !== skill))}>
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ',') {
                        e.preventDefault();
                        addSkill();
                      }
                    }}
                    onBlur={addSkill}
                    className="text-xs bg-transparent outline-none w-24"
                    style={{ color: 'var(--color-text-muted)' }}
                    placeholder="+ skill"
                  />
                </div>
              </div>

              {/* Time commitment */}
              <div className="flex items-center gap-2">
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Time commitment:</span>
                <select
                  value={editTimeCommitment}
                  onChange={(e) => setEditTimeCommitment(e.target.value)}
                  className="text-xs rounded-md border px-2 py-1 outline-none"
                  style={{
                    borderColor: 'var(--color-border)',
                    color: 'var(--color-text-secondary)',
                    backgroundColor: 'var(--color-surface-white)',
                  }}
                >
                  <option value="A few hours">A few hours</option>
                  <option value="Half a day">Half a day</option>
                  <option value="A full day">A full day</option>
                  <option value="Multiple days">Multiple days</option>
                </select>
              </div>

              {error && (
                <p className="text-xs" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={handleSave}
                  disabled={saving || !editTitle.trim() || !editProblem.trim()}
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
                  onClick={() => { setEditing(false); setError(null); }}
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
                <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {collab.title}
                </h1>
                {isAuthor && (
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={startEditing}
                      className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors hover:bg-[var(--color-surface-raised)]"
                      title="Edit"
                      aria-label="Edit"
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
                        title="Delete"
                        aria-label="Delete"
                      >
                        <Trash2 className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Author row: profile + dept + status + time */}
              <div className="flex flex-wrap items-center gap-2 mb-5">
                <ProfileChip userId={collab.author_id} avatarSize={24} />
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: 'var(--color-surface-raised)',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  {formatDepartmentName(collab.department)}
                </span>
                <StatusBadge status={collab.status} />
                <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {relativeTime(collab.created_at)}
                </span>
              </div>

              {/* Problem text */}
              <p className="text-base mb-5 whitespace-pre-wrap" style={{ color: 'var(--color-text-primary)' }}>
                {collab.problem}
              </p>

              {/* Time commitment */}
              {collab.time_commitment && (
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Time commitment:</span>
                  <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{collab.time_commitment}</span>
                </div>
              )}

              {/* Needed skills */}
              {collab.needed_skills.length > 0 && (
                <div className="flex items-center flex-wrap gap-1.5 mb-5">
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Needs:</span>
                  {collab.needed_skills.map((skill) => (
                    <span
                      key={skill}
                      className="text-xs px-2.5 py-1 rounded-full"
                      style={{
                        border: '1px solid var(--color-primary)',
                        backgroundColor: 'transparent',
                        color: 'var(--color-primary)',
                      }}
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              )}

              {/* Interested section */}
              <div
                className="rounded-lg border p-4 mb-5"
                style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface)' }}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    {interestedIds.length > 0
                      ? `${interestedIds.length} Interested`
                      : 'No one has expressed interest yet'}
                  </span>
                  <button
                    onClick={handleInterestToggle}
                    disabled={interestLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-150 border disabled:opacity-50"
                    style={
                      interested
                        ? {
                            backgroundColor: 'var(--color-primary)',
                            borderColor: 'var(--color-primary)',
                            color: '#fff',
                          }
                        : {
                            backgroundColor: 'transparent',
                            borderColor: 'var(--color-primary)',
                            color: 'var(--color-primary)',
                          }
                    }
                  >
                    <HandHeart className="w-4 h-4" strokeWidth={1.5} />
                    {interested ? "I'm Interested" : "I'm Interested"}
                  </button>
                </div>

                {interestedIds.length > 0 && (
                  <div className="space-y-2">
                    {interestedIds.map((uid) => (
                      <div key={uid} className="flex items-center gap-2">
                        <ProfileChip userId={uid} avatarSize={24} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Status controls (author only) */}
              {isAuthor && (
                <div className="flex items-center gap-2 mb-5">
                  <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Change status:</span>
                  <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: 'var(--color-border)' }}>
                    {STATUS_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => handleStatusChange(opt.value)}
                        disabled={statusLoading || collab.status === opt.value}
                        className="text-sm px-2.5 py-1.5 transition-colors duration-150 border-l first:border-l-0 disabled:opacity-50"
                        style={{
                          borderColor: 'var(--color-border)',
                          backgroundColor: collab.status === opt.value ? 'var(--color-primary-subtle)' : 'var(--color-surface-white)',
                          color: collab.status === opt.value ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                          fontWeight: collab.status === opt.value ? 500 : 400,
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <p className="text-xs mb-3" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
              )}

              {/* Comments section */}
              <div className="mt-6 pt-6" style={{ borderTop: '1px solid var(--color-border)' }}>
                <div className="flex items-center gap-2 mb-4">
                  <MessageSquare className="w-4 h-4" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
                  <span className="text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                    {commentsLoading ? 'Comments' : `${comments.length} Comment${comments.length !== 1 ? 's' : ''}`}
                  </span>
                </div>

                {comments.length > 0 && (
                  <div className="space-y-4 mb-5">
                    {comments.map((comment) => (
                      <div key={comment.comment_id}>
                        <div className="flex items-center gap-2 mb-1">
                          <ProfileChip userId={comment.author_id} avatarSize={24} />
                          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                            {relativeTime(comment.created_at)}
                          </span>
                          {isOwnComment(comment.author_id) && (
                            <div className="flex items-center gap-0.5 ml-auto">
                              {confirmDeleteCommentId === comment.comment_id ? (
                                <div className="flex items-center gap-1 ml-1">
                                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Delete?</span>
                                  <button
                                    onClick={() => handleDeleteComment(comment.comment_id)}
                                    disabled={deleteCommentInProgress}
                                    className="text-xs font-medium px-1.5 py-0.5 rounded"
                                    style={{ color: '#DC2626', backgroundColor: '#FEE2E2' }}
                                  >
                                    {deleteCommentInProgress ? '...' : 'Yes'}
                                  </button>
                                  <button
                                    onClick={() => setConfirmDeleteCommentId(null)}
                                    disabled={deleteCommentInProgress}
                                    className="text-xs font-medium px-1.5 py-0.5 rounded"
                                    style={{ color: 'var(--color-text-secondary)' }}
                                  >
                                    No
                                  </button>
                                </div>
                              ) : (
                                <button
                                  onClick={() => setConfirmDeleteCommentId(comment.comment_id)}
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
                        <p className="text-sm whitespace-pre-wrap pl-[30px]" style={{ color: 'var(--color-text-primary)' }}>
                          {comment.content}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {!commentsLoading && comments.length === 0 && (
                  <p className="text-xs mb-4" style={{ color: 'var(--color-text-muted)' }}>
                    No comments yet. Start the discussion.
                  </p>
                )}

                {user && (
                  <form onSubmit={handleCommentSubmit} className="flex gap-2">
                    <textarea
                      value={commentContent}
                      onChange={(e) => setCommentContent(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                          e.preventDefault();
                          handleCommentSubmit(e);
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
                      disabled={commentSubmitting}
                    />
                    <button
                      type="submit"
                      disabled={commentSubmitting || !commentContent.trim()}
                      className="self-end flex items-center justify-center w-9 h-9 rounded-lg transition-colors duration-100 disabled:opacity-40"
                      style={{ backgroundColor: 'var(--color-primary)', color: '#fff' }}
                      title="Post comment"
                      aria-label="Post comment"
                    >
                      {commentSubmitting ? (
                        <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
                      ) : (
                        <Send className="w-4 h-4" strokeWidth={1.5} />
                      )}
                    </button>
                  </form>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
