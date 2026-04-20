/**
 * CollabPreviewCard - Editable preview card for collabs before publishing.
 *
 * Shows the AI-drafted collab with editable title, problem description,
 * needed skills (pill editor), time commitment dropdown, tags, and
 * read-only department. Follows the same edit/preview toggle pattern
 * as TipPreviewCard.
 */

import { useState } from 'react';
import { X, Check, Users } from 'lucide-react';
import { createCollab } from '../api/client';

const TIME_COMMITMENTS = [
  'A few hours',
  'Half a day',
  'A full day',
  'Multiple AI Tuesdays',
];

interface CollabPreviewCardProps {
  initial: {
    title: string;
    problem: string;
    needed_skills: string[];
    time_commitment: string;
    tags: string[];
    department: string;
    tool_call_id?: string;
  };
  sessionId?: string;
  onPublished: () => void;
  onShowCollabs?: () => void;
}

export function CollabPreviewCard({ initial, sessionId, onPublished }: CollabPreviewCardProps) {
  const [title, setTitle] = useState(initial.title);
  const [problem, setProblem] = useState(initial.problem);
  const [neededSkills, setNeededSkills] = useState<string[]>(
    Array.isArray(initial.needed_skills) ? initial.needed_skills
    : typeof initial.needed_skills === 'string' ? (initial.needed_skills as string).split(',').map(s => s.trim()).filter(Boolean)
    : []
  );
  const [timeCommitment, setTimeCommitment] = useState(initial.time_commitment || 'A few hours');
  const [tags, setTags] = useState<string[]>(initial.tags);
  const [department] = useState(initial.department || 'Everyone');
  const [skillInput, setSkillInput] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addSkill() {
    const s = skillInput.trim();
    if (s && !neededSkills.includes(s)) {
      setNeededSkills([...neededSkills, s]);
    }
    setSkillInput('');
  }

  function addTag() {
    const t = tagInput.trim().toLowerCase();
    if (t && !tags.includes(t)) {
      setTags([...tags, t]);
    }
    setTagInput('');
  }

  async function handlePublish() {
    if (!title.trim() || !problem.trim()) return;

    setPublishing(true);
    setError(null);
    try {
      await createCollab({
        title,
        problem,
        needed_skills: neededSkills,
        time_commitment: timeCommitment,
        tags,
        department,
        source_session_id: sessionId || '',
        source_tool_call_id: initial.tool_call_id || '',
      });
      onPublished();
    } catch (err) {
      console.error('Failed to publish collab:', err);
      setError('Failed to publish. Please try again.');
      setPublishing(false);
    }
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
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4" style={{ color: 'var(--color-primary)' }} strokeWidth={1.5} />
            <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Review your collab
            </span>
          </div>
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
            placeholder="Collab title..."
          />
        ) : (
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {title}
          </h3>
        )}

        {/* Problem */}
        {isEditing ? (
          <textarea
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            rows={4}
            className="w-full text-sm bg-transparent border rounded-lg outline-none p-3 resize-y"
            style={{
              color: 'var(--color-text-primary)',
              borderColor: 'var(--color-border)',
              fontFamily: 'inherit',
            }}
            placeholder="Describe the problem you want to solve..."
          />
        ) : (
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            {problem}
          </p>
        )}

        {/* Needed Skills */}
        <div>
          <span className="text-xs font-medium block mb-1.5" style={{ color: 'var(--color-text-muted)' }}>
            Needs:
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {neededSkills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                style={{
                  border: '1px solid var(--color-primary)',
                  backgroundColor: 'transparent',
                  color: 'var(--color-primary)',
                }}
              >
                {skill}
                {isEditing && (
                  <button onClick={() => setNeededSkills(neededSkills.filter((s) => s !== skill))}>
                    <X className="w-3 h-3" />
                  </button>
                )}
              </span>
            ))}
            {isEditing && (
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
            )}
          </div>
        </div>

        {/* Time Commitment */}
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Time:</span>
          {isEditing ? (
            <select
              value={timeCommitment}
              onChange={(e) => setTimeCommitment(e.target.value)}
              className="text-xs rounded-md border px-2 py-1 outline-none"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-secondary)',
                backgroundColor: 'var(--color-surface-white)',
              }}
            >
              {TIME_COMMITMENTS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          ) : (
            <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {timeCommitment}
            </span>
          )}
        </div>

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

        {/* Department (read-only) */}
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Department:</span>
          <span className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>
            {department}
          </span>
        </div>
      </div>

      {/* Error + Publish button */}
      <div className="px-5 pb-4">
        {error && (
          <p className="text-xs mb-2" style={{ color: 'var(--color-error, #DC2626)' }}>{error}</p>
        )}
        <button
          onClick={handlePublish}
          disabled={publishing || !title.trim() || !problem.trim()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          {publishing ? (
            <>
              <div className="w-4 h-4 border-2 border-t-transparent border-white rounded-full animate-spin" />
              Publishing...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" strokeWidth={2} />
              Publish Collab
            </>
          )}
        </button>
      </div>
    </div>
  );
}
