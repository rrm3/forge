/**
 * IdeaPreviewCard - Editable preview card for user ideas before saving.
 *
 * Shows the AI-drafted idea with editable title, description (markdown),
 * and tags. User can edit and then save or skip.
 */

import { useState, useRef } from 'react';
import { Bold, Italic, List, X, Bookmark } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { createUserIdea } from '../api/client';

interface IdeaPreviewCardProps {
  initial: { title: string; description: string; tags: string[] };
  sessionId: string;
  onSaved: (saved?: { idea_id: string; title: string; description: string; tags: string[] }) => void;
  onSkip: () => void;
}

export function IdeaPreviewCard({ initial, sessionId, onSaved, onSkip }: IdeaPreviewCardProps) {
  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description);
  const [tags, setTags] = useState<string[]>(initial.tags);
  const [tagInput, setTagInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function wrapSelection(before: string, after: string) {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = description.substring(start, end);
    const newDescription = description.substring(0, start) + before + selected + after + description.substring(end);
    setDescription(newDescription);
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

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const result = await createUserIdea({
        title,
        description,
        tags,
        source: 'brainstorm',
        source_session_id: sessionId,
      });
      setSaved(true);
      setSaving(false);
      onSaved({ idea_id: result.idea_id, title, description, tags });
    } catch (err) {
      console.error('Failed to save idea:', err);
      setError('Failed to save. Please try again.');
      setSaving(false);
    }
  }

  return (
    <div
      className="my-4 mx-auto max-w-[95%] md:max-w-[85%] rounded-xl border overflow-hidden"
      style={{ backgroundColor: 'var(--color-surface-white)', borderColor: 'var(--color-border)' }}
    >
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Idea to explore
          </span>
          {!saved && (
            <div className="flex items-center gap-2">
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
              <button
                onClick={onSkip}
                className="text-xs font-medium px-2 py-1 rounded-md transition-colors hover:bg-[var(--color-surface-raised)]"
                style={{ color: 'var(--color-text-muted)' }}
                title="Dismiss"
              >
                <X className="w-3.5 h-3.5" strokeWidth={2} />
              </button>
            </div>
          )}
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
            placeholder="Idea title..."
          />
        ) : (
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h3>
        )}

        {/* Description */}
        {isEditing ? (
          <div>
            {/* Formatting toolbar */}
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
                  const lineStart = description.lastIndexOf('\n', start - 1) + 1;
                  setDescription(description.substring(0, lineStart) + '- ' + description.substring(lineStart));
                }}
                className="p-1 rounded hover:bg-[var(--color-surface-raised)]"
                title="List"
              >
                <List className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={2} />
              </button>
            </div>
            <textarea
              ref={textareaRef}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
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
          <div className="prose prose-sm max-w-none text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{description}</ReactMarkdown>
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
      </div>

      {/* Error + Action buttons */}
      <div className="px-5 pb-4">
        {error && (
          <p className="text-xs mb-2" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
        )}
        {saved ? (
          <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-success, #059669)' }}>
            <Bookmark className="w-4 h-4" strokeWidth={2} />
            <span className="font-medium">Saved to your Ideas</span>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !title.trim() || !description.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
              style={{ backgroundColor: 'var(--color-primary)' }}
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
              ) : (
                <Bookmark className="w-4 h-4" strokeWidth={2} />
              )}
              {saving ? 'Saving...' : 'Save Idea'}
            </button>
            <button
              onClick={onSkip}
              className="text-sm font-medium transition-colors"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Skip
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
