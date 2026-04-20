/**
 * TipPreviewCard - Editable preview card for tips before publishing.
 *
 * Shows the AI-drafted tip with editable title, content (markdown), tags,
 * and department selector. Includes duplicate detection with a shake
 * animation and friendly messaging when similar content is found.
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bold, Italic, List, X, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { createTip, checkSimilarTips, addTipComment } from '../api/client';
import type { SimilarMatch } from '../api/types';
import { ProfileChip } from './ProfileChip';
import { useProfileCache } from '../state/profileCache';

const DEPARTMENTS = [
  'Everyone',
  'Chief Of Staff', 'Customer Solutions', 'Customer Success',
  'Finance', 'Global', 'Legal', 'Marketing',
  'Operations', 'People', 'Product', 'Sales', 'Technology',
];

interface TipPreviewCardProps {
  initial: { title: string; content: string; tags: string[]; department: string; category?: string; tool_call_id?: string };
  sessionId?: string;
  onPublished: () => void;
  onShowTips?: () => void;
}

export function TipPreviewCard({ initial, sessionId, onPublished }: TipPreviewCardProps) {
  const [title, setTitle] = useState(initial.title);
  const [content, setContent] = useState(initial.content);
  const [tags, setTags] = useState<string[]>(initial.tags);
  const [department, setDepartment] = useState(initial.department || 'Everyone');
  const [tagInput, setTagInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Duplicate detection state
  const [matches, setMatches] = useState<SimilarMatch[] | null>(null);
  const [editingComment, setEditingComment] = useState<Record<string, string>>({});
  const [commentPostedTipId, setCommentPostedTipId] = useState<string | null>(null);
  const [shaking, setShaking] = useState(false);

  function wrapSelection(before: string, after: string) {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = content.substring(start, end);
    const newContent = content.substring(0, start) + before + selected + after + content.substring(end);
    setContent(newContent);
    requestAnimationFrame(() => {
      ta.focus();
      ta.selectionStart = start + before.length;
      ta.selectionEnd = end + before.length;
    });
  }

  function addTag() {
    const t = tagInput.trim().toLowerCase();
    if (t && !tags.includes(t)) {
      setTags([...tags, t]);
    }
    setTagInput('');
  }

  async function handlePublish() {
    if (!title.trim() || !content.trim()) return;

    setChecking(true);
    setError(null);
    try {
      const result = await checkSimilarTips({ title, content });
      if (result.matches.length > 0) {
        setMatches(result.matches);
        const comments: Record<string, string> = {};
        for (const m of result.matches) {
          if (m.suggested_comment) {
            comments[m.tip.tip_id] = m.suggested_comment;
          }
        }
        setEditingComment(comments);
        setShaking(true);
        setTimeout(() => setShaking(false), 600);
        setChecking(false);
        return;
      }
    } catch {
      // If duplicate check fails, proceed with publish anyway
    }
    setChecking(false);
    await doPublish();
  }

  async function doPublish() {
    setPublishing(true);
    try {
      await createTip({
        title,
        content,
        tags,
        department,
        category: initial.category || 'tip',
        source_session_id: sessionId || '',
        source_tool_call_id: initial.tool_call_id || '',
      });
      onPublished();
    } catch (err) {
      console.error('Failed to publish tip:', err);
      setError('Failed to publish. Please try again.');
      setPublishing(false);
    }
  }

  async function handleAddToDiscussion(tipId: string) {
    const commentText = editingComment[tipId];
    if (!commentText?.trim()) return;

    setPublishing(true);
    setError(null);
    try {
      await addTipComment(tipId, commentText);
      setCommentPostedTipId(tipId);
      setPublishing(false);
    } catch (err) {
      console.error('Failed to add comment:', err);
      setError('Failed to post comment. Please try again.');
      setPublishing(false);
    }
  }

  // Comment posted confirmation
  const navigate = useNavigate();
  if (commentPostedTipId) {
    return (
      <div
        className="my-4 mx-auto max-w-[95%] md:max-w-[85%] rounded-xl border overflow-hidden"
        style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
      >
        <div className="px-5 py-6 text-center">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-3"
            style={{ backgroundColor: 'var(--color-primary-subtle)' }}
          >
            <Check className="w-5 h-5" style={{ color: 'var(--color-primary)' }} strokeWidth={2} />
          </div>
          <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
            Comment added
          </p>
          <p className="text-xs mb-3" style={{ color: 'var(--color-text-secondary)' }}>
            Your perspective has been added to the existing discussion.
          </p>
          <button
            onClick={() => navigate(`/tips/${commentPostedTipId}`)}
            className="text-sm font-medium px-3 py-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-subtle)' }}
          >
            View the discussion
          </button>
        </div>
      </div>
    );
  }

  // Duplicate detection results - with shake animation
  if (matches && matches.length > 0) {
    return (
      <>
        <style>{`
          @keyframes tip-shake {
            0%, 100% { transform: translateX(0); }
            15% { transform: translateX(-6px); }
            30% { transform: translateX(5px); }
            45% { transform: translateX(-4px); }
            60% { transform: translateX(3px); }
            75% { transform: translateX(-2px); }
            90% { transform: translateX(1px); }
          }
        `}</style>
        <div
          className="my-4 mx-auto max-w-[95%] md:max-w-[85%] rounded-xl border-2 overflow-hidden"
          style={{
            backgroundColor: 'var(--color-surface-white)',
            borderColor: 'var(--color-primary)',
            animation: shaking ? 'tip-shake 0.5s ease-in-out' : undefined,
          }}
        >
          <div className="px-5 pt-4 pb-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Great minds think alike!
            </span>
          </div>
          <div className="px-5 py-4">
            <p className="text-xs mb-4" style={{ color: 'var(--color-text-secondary)' }}>
              It looks like someone posted something very similar. You can add your take as a comment on theirs, or publish yours as a new tip if it's different enough.
            </p>

            <div className="space-y-3 mb-4">
              {matches.map((match) => (
                <div
                  key={match.tip.tip_id}
                  className="rounded-lg border p-3"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <ProfileChip userId={match.tip.author_id} avatarSize={18} />
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {Math.round(match.confidence * 100)}% similar
                    </span>
                  </div>
                  <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    {match.tip.title}
                  </p>
                  <p className="text-xs mb-2" style={{ color: 'var(--color-text-secondary)' }}>
                    {match.explanation}
                  </p>

                  {editingComment[match.tip.tip_id] !== undefined && (
                    <div className="mb-2">
                      <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                        Your comment:
                      </label>
                      <AutoSizeTextarea
                        value={editingComment[match.tip.tip_id]}
                        onChange={(e) => setEditingComment({ ...editingComment, [match.tip.tip_id]: e.target.value })}
                      />
                    </div>
                  )}

                  <CommentButton
                    authorId={match.tip.author_id}
                    onClick={() => handleAddToDiscussion(match.tip.tip_id)}
                    disabled={publishing || !editingComment[match.tip.tip_id]?.trim()}
                  />
                </div>
              ))}
            </div>

            {error && (
              <p className="text-xs mb-2" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={doPublish}
                disabled={publishing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
                style={{ backgroundColor: 'var(--color-primary)' }}
              >
                {publishing ? (
                  <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
                ) : null}
                Publish as New
              </button>
              <button
                onClick={() => setMatches(null)}
                className="px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Back to editing
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // Main edit/preview card
  return (
    <div
      className="my-4 mx-auto max-w-[95%] md:max-w-[85%] rounded-xl border overflow-hidden"
      style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Review your tip
          </span>
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="text-xs font-medium px-2 py-1 rounded-md transition-colors"
            style={{
              color: isEditing ? 'var(--color-primary)' : 'var(--color-text-muted)',
              backgroundColor: isEditing ? 'var(--color-primary-subtle)' : 'transparent',
            }}
          >
            {isEditing ? 'Preview' : 'Edit'}
          </button>
        </div>
      </div>

      <div className="px-5 py-4 space-y-3">
        {/* Title */}
        {isEditing ? (
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full text-base font-semibold bg-transparent border-b outline-none pb-1"
            style={{ color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}
            placeholder="Tip title..."
          />
        ) : (
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h3>
        )}

        {/* Content */}
        {isEditing ? (
          <div>
            <div className="flex items-center gap-1 mb-1">
              <button
                onClick={() => wrapSelection('**', '**')}
                className="p-1 rounded hover:bg-[var(--color-surface-raised)]"
                title="Bold"
              >
                <Bold className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
              </button>
              <button
                onClick={() => wrapSelection('*', '*')}
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
                  const lineStart = content.lastIndexOf('\n', start - 1) + 1;
                  setContent(content.substring(0, lineStart) + '- ' + content.substring(lineStart));
                }}
                className="p-1 rounded hover:bg-[var(--color-surface-raised)]"
                title="List"
              >
                <List className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
              </button>
            </div>
            <textarea
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={6}
              className="w-full text-sm bg-transparent border rounded-lg outline-none p-3 resize-y"
              style={{
                color: 'var(--color-text-primary)',
                borderColor: 'var(--color-border)',
                fontFamily: 'inherit',
              }}
              placeholder="Write your tip in markdown..."
            />
          </div>
        ) : (
          <div className="prose prose-sm max-w-none text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        )}

        {/* Tags */}
        <div className="flex flex-wrap items-center gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
              style={{ backgroundColor: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' }}
            >
              {tag}
              {isEditing && (
                <button onClick={() => setTags(tags.filter((t) => t !== tag))}>
                  <X className="w-3 h-3" />
                </button>
              )}
            </span>
          ))}
          {isEditing && (
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
          )}
        </div>

        {/* Department selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Share with:</span>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
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
      </div>

      {/* Error + Publish button */}
      <div className="px-5 pb-4">
        {error && (
          <p className="text-xs mb-2" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
        )}
        <button
          onClick={handlePublish}
          disabled={publishing || checking || !title.trim() || !content.trim()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          {checking ? (
            <>
              <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
              Checking...
            </>
          ) : publishing ? (
            <>
              <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
              Publishing...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" strokeWidth={2} />
              Publish Tip
            </>
          )}
        </button>
      </div>
    </div>
  );
}

/** Button that shows "Post a Comment on {Name}'s Tip" using the profile cache */
function CommentButton({ authorId, onClick, disabled }: { authorId: string; onClick: () => void; disabled: boolean }) {
  const profile = useProfileCache((s) => s.profiles[authorId]);
  const firstName = profile?.name?.split(' ')[0] || 'Their';

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="text-xs font-medium px-2.5 py-1 rounded-md transition-colors disabled:opacity-50"
      style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-subtle)' }}
    >
      Post a Comment on {firstName}'s Tip
    </button>
  );
}

/** Textarea that auto-sizes to fit its content */
function AutoSizeTextarea({ value, onChange }: { value: string; onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void }) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = ref.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    }
  }, [value]);

  return (
    <textarea
      ref={ref}
      value={value}
      onChange={onChange}
      className="w-full text-sm border rounded-lg outline-none p-3 resize-none leading-relaxed"
      style={{
        borderColor: 'var(--color-border)',
        color: 'var(--color-text-primary)',
        backgroundColor: 'var(--color-surface)',
        minHeight: '80px',
      }}
    />
  );
}
