/**
 * TipPreviewCard - Editable preview card for tips before publishing.
 *
 * Shows the AI-drafted tip with editable title, content (markdown), tags,
 * and department selector. User can edit and then publish.
 */

import { useState, useRef } from 'react';
import { Bold, Italic, List, X, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { createTip } from '../api/client';

const DEPARTMENTS = [
  'Everyone',
  'Chief Of Staff', 'Customer Solutions', 'Customer Success',
  'Finance', 'Global', 'Legal', 'Marketing',
  'Operations', 'People', 'Product', 'Sales', 'Technology',
];

interface TipPreviewCardProps {
  initial: { title: string; content: string; tags: string[]; department: string };
  onPublished: () => void;
  onShowTips?: () => void;
}

export function TipPreviewCard({ initial, onPublished }: TipPreviewCardProps) {
  const [title, setTitle] = useState(initial.title);
  const [content, setContent] = useState(initial.content);
  const [tags, setTags] = useState<string[]>(initial.tags);
  const [department, setDepartment] = useState(initial.department || 'Everyone');
  const [tagInput, setTagInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    setPublishing(true);
    try {
      await createTip({ title, content, tags, department });
      onPublished();
    } catch (err) {
      console.error('Failed to publish tip:', err);
      setError('Failed to publish. Please try again.');
      setPublishing(false);
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
      </div>
      <div className="px-5 pb-4">
        <button
          onClick={handlePublish}
          disabled={publishing || !title.trim() || !content.trim()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          {publishing ? (
            <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
          ) : (
            <Check className="w-4 h-4" strokeWidth={2} />
          )}
          {publishing ? 'Publishing...' : 'Publish Tip'}
        </button>
      </div>
    </div>
  );
}
