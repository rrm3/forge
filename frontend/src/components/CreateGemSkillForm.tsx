/**
 * CreateGemSkillForm - Form for creating Gemini Gems and Claude Skills.
 *
 * Unlike General Tips (which use the chat-assisted flow), gems and skills
 * are artifacts people already have. This form lets them paste the content,
 * add metadata, and publish. Includes duplicate detection before publishing.
 */

import { useState } from 'react';
import { ArrowLeft, X, Check, Info } from 'lucide-react';
import { createTip, checkSimilarTips, addTipComment } from '../api/client';
import type { TipCategory, SimilarMatch } from '../api/types';
import { ProfileChip } from './ProfileChip';
import { GeminiIcon, ClaudeIcon } from './AiIcons';

const DEPARTMENTS = [
  'Everyone',
  'Chief Of Staff', 'Customer Solutions', 'Customer Success',
  'Finance', 'Global', 'Legal', 'Marketing',
  'Operations', 'People', 'Product', 'Sales', 'Technology',
];

const CATEGORY_META: Record<string, { title: string; artifactLabel: string; artifactPlaceholder: string }> = {
  gem: {
    title: 'Share a Gemini Gem',
    artifactLabel: 'Gem Instructions',
    artifactPlaceholder: 'Paste the full Gemini Gem prompt or instructions here...',
  },
  skill: {
    title: 'Share a Claude Skill',
    artifactLabel: 'Skill Definition',
    artifactPlaceholder: 'Paste the Claude skill definition or markdown here...',
  },
};

interface CreateGemSkillFormProps {
  category: 'gem' | 'skill';
  onBack: () => void;
  onPublished: () => void;
}

export function CreateGemSkillForm({ category, onBack, onPublished }: CreateGemSkillFormProps) {
  const meta = CATEGORY_META[category];

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [artifact, setArtifact] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');
  const [department, setDepartment] = useState('Everyone');
  const [publishing, setPublishing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Duplicate detection state
  const [matches, setMatches] = useState<SimilarMatch[] | null>(null);
  const [editingComment, setEditingComment] = useState<Record<string, string>>({});
  const [commentPosted, setCommentPosted] = useState<string | null>(null);

  function addTag() {
    const t = tagInput.trim().toLowerCase();
    if (t && !tags.includes(t)) {
      setTags([...tags, t]);
    }
    setTagInput('');
  }

  async function handlePublishClick() {
    if (!title.trim() || !content.trim()) return;

    // First check for duplicates
    setChecking(true);
    setError(null);
    try {
      const result = await checkSimilarTips({ title, content, artifact });
      if (result.matches.length > 0) {
        setMatches(result.matches);
        // Pre-populate editable comments
        const comments: Record<string, string> = {};
        for (const m of result.matches) {
          if (m.suggested_comment) {
            comments[m.tip.tip_id] = m.suggested_comment;
          }
        }
        setEditingComment(comments);
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
    setError(null);
    try {
      await createTip({ title, content, tags, department, category, artifact });
      onPublished();
    } catch (err) {
      console.error('Failed to publish:', err);
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
      setCommentPosted(tipId);
      setPublishing(false);
    } catch (err) {
      console.error('Failed to add comment:', err);
      setError('Failed to post comment. Please try again.');
      setPublishing(false);
    }
  }

  const canPublish = title.trim() && content.trim() && !publishing && !checking;

  // Duplicate detection results view
  if (matches && matches.length > 0 && !commentPosted) {
    return (
      <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
        <div className="flex-1 overflow-y-auto px-4 md:px-6 py-5">
          <div className="max-w-2xl mx-auto">
            <button
              onClick={() => setMatches(null)}
              className="flex items-center gap-2 mb-5 transition-colors duration-150 hover:opacity-70"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
              <span className="text-sm font-medium">Back to editing</span>
            </button>

            <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Similar content already shared
            </h2>
            <p className="text-sm mb-5" style={{ color: 'var(--color-text-secondary)' }}>
              We found existing items that cover similar ground. You can add your perspective as a comment, or publish as new if yours is different enough.
            </p>

            <div className="space-y-4 mb-6">
              {matches.map((match) => (
                <div
                  key={match.tip.tip_id}
                  className="rounded-xl border p-4"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <ProfileChip userId={match.tip.author_id} avatarSize={20} />
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {Math.round(match.confidence * 100)}% similar
                    </span>
                  </div>
                  <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    {match.tip.title}
                  </p>
                  <p className="text-sm mb-3" style={{ color: 'var(--color-text-secondary)' }}>
                    {match.explanation}
                  </p>

                  {/* Editable suggested comment */}
                  {editingComment[match.tip.tip_id] && (
                    <div className="mb-3">
                      <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--color-text-muted)' }}>
                        Your comment (editable):
                      </label>
                      <textarea
                        value={editingComment[match.tip.tip_id]}
                        onChange={(e) => setEditingComment({ ...editingComment, [match.tip.tip_id]: e.target.value })}
                        rows={3}
                        className="w-full text-sm border rounded-lg outline-none p-2.5 resize-y"
                        style={{
                          borderColor: 'var(--color-border)',
                          color: 'var(--color-text-primary)',
                          backgroundColor: 'var(--color-surface)',
                        }}
                      />
                    </div>
                  )}

                  <button
                    onClick={() => handleAddToDiscussion(match.tip.tip_id)}
                    disabled={publishing || !editingComment[match.tip.tip_id]?.trim()}
                    className="text-sm font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                    style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-subtle)' }}
                  >
                    Add to Discussion
                  </button>
                </div>
              ))}
            </div>

            {error && (
              <p className="text-xs mb-3" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
            )}

            <div className="flex items-center gap-3">
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
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Comment posted confirmation
  if (commentPosted) {
    return (
      <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
        <div className="flex-1 flex items-center justify-center px-4 md:px-6">
          <div className="text-center max-w-sm">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: 'var(--color-primary-subtle)' }}
            >
              <Check className="w-6 h-6" style={{ color: 'var(--color-primary)' }} strokeWidth={2} />
            </div>
            <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Comment added
            </h2>
            <p className="text-sm mb-5" style={{ color: 'var(--color-text-secondary)' }}>
              Your perspective has been added to the existing discussion. Thanks for enriching the knowledge base!
            </p>
            <button
              onClick={onBack}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white"
              style={{ backgroundColor: 'var(--color-primary)' }}
            >
              Back to Tips & Tricks
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Main form
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
            <span className="text-sm font-medium">Back to Tips & Tricks</span>
          </button>

          <h1 className="flex items-center gap-2 text-xl font-semibold mb-5" style={{ color: 'var(--color-text-primary)' }}>
            {category === 'gem' ? <GeminiIcon size={22} /> : <ClaudeIcon size={22} />}
            {meta.title}
          </h1>

          {/* Claude Skills availability notice */}
          {category === 'skill' && (
            <div
              className="flex items-start gap-3 mb-5 px-4 py-3 rounded-lg border"
              style={{ backgroundColor: 'var(--color-primary-subtle)', borderColor: 'var(--color-primary)' }}
            >
              <Info className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: 'var(--color-primary)' }} strokeWidth={1.5} />
              <p className="text-sm" style={{ color: 'var(--color-text-primary)' }}>
                Claude is not yet available to all users, but is coming soon!
              </p>
            </div>
          )}

          <div className="space-y-5">
            {/* Title */}
            <div>
              <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full text-sm border rounded-lg outline-none px-3 py-2.5"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                  backgroundColor: 'var(--color-surface-white)',
                }}
                placeholder="Give it a clear, descriptive name..."
                maxLength={200}
              />
            </div>

            {/* Description */}
            <div>
              <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                Description
              </label>
              <p className="text-xs mb-1.5" style={{ color: 'var(--color-text-muted)' }}>
                What does this {category === 'gem' ? 'gem' : 'skill'} do? Who is it useful for?
              </p>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={4}
                className="w-full text-sm border rounded-lg outline-none p-3 resize-y"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                  backgroundColor: 'var(--color-surface-white)',
                  fontFamily: 'inherit',
                }}
                placeholder="Describe what it does and when to use it..."
                maxLength={10000}
              />
            </div>

            {/* Artifact */}
            <div>
              <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                {meta.artifactLabel}
              </label>
              <p className="text-xs mb-1.5" style={{ color: 'var(--color-text-muted)' }}>
                Paste the full {category === 'gem' ? 'gem prompt/instructions' : 'skill definition'} below
              </p>
              <textarea
                value={artifact}
                onChange={(e) => setArtifact(e.target.value)}
                rows={10}
                className="w-full text-sm border rounded-lg outline-none p-3 resize-y font-mono"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                  backgroundColor: 'var(--color-surface)',
                  fontSize: '13px',
                  lineHeight: '1.5',
                }}
                placeholder={meta.artifactPlaceholder}
                maxLength={50000}
              />
            </div>

            {/* Tags */}
            <div>
              <label className="text-sm font-medium mb-1.5 block" style={{ color: 'var(--color-text-primary)' }}>
                Tags
              </label>
              <div className="flex flex-wrap items-center gap-1.5">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                    style={{ backgroundColor: 'var(--color-surface-raised)', color: 'var(--color-text-muted)' }}
                  >
                    {tag}
                    <button onClick={() => setTags(tags.filter((t) => t !== tag))}>
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
                  className="text-xs bg-transparent outline-none w-24"
                  style={{ color: 'var(--color-text-muted)' }}
                  placeholder="+ add tag"
                />
              </div>
            </div>

            {/* Department */}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                Share with:
              </span>
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="text-sm rounded-lg border px-3 py-1.5 outline-none"
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

            {/* Publish button */}
            <button
              onClick={handlePublishClick}
              disabled={!canPublish}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
              style={{ backgroundColor: 'var(--color-primary)' }}
            >
              {checking ? (
                <>
                  <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
                  Checking for similar content...
                </>
              ) : publishing ? (
                <>
                  <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
                  Publishing...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" strokeWidth={2} />
                  Publish {category === 'gem' ? 'Gem' : 'Skill'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
