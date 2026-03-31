import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ThumbsUp, Plus, Lightbulb, MessageCircle } from 'lucide-react';
import { listTips, voteTip, unvoteTip } from '../api/client';
import type { Tip, TipCategory } from '../api/types';
import { CreateGemSkillForm } from './CreateGemSkillForm';
import { ProfileChip } from './ProfileChip';
import { GeminiIcon, ClaudeIcon } from './AiIcons';
import { useSession } from '../state/SessionContext';


const DEPARTMENTS = [
  'chief-of-staff',
  'customer-solutions',
  'customer-success',
  'finance',
  'global',
  'legal',
  'marketing',
  'operations',
  'people',
  'product',
  'sales',
  'technology',
];

type CategoryFilter = 'all' | TipCategory;

const CATEGORY_TABS: { value: CategoryFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'tip', label: 'General Tips' },
  { value: 'gem', label: 'Gemini Gems' },
  { value: 'skill', label: 'Claude Skills' },
];

const CATEGORY_LABELS: Record<string, string> = {
  tip: 'General Tip',
  gem: 'Gemini Gem',
  skill: 'Claude Skill',
};

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  tip: { bg: 'var(--color-surface-raised)', text: 'var(--color-text-muted)' },
  gem: { bg: 'var(--color-surface-raised)', text: 'var(--color-text-muted)' },
  skill: { bg: 'var(--color-surface-raised)', text: 'var(--color-text-muted)' },
};

function formatDepartmentName(slug: string): string {
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function stripMarkdown(md: string): string {
  return md
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/\n{2,}/g, ' ')
    .replace(/\n/g, ' ')
    .trim();
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

export function TipsView() {
  const navigate = useNavigate();
  const { startTypedSession } = useSession();
  const [tips, setTips] = useState<Tip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [department, setDepartment] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'recent' | 'popular'>('recent');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [showCreateForm, setShowCreateForm] = useState<'gem' | 'skill' | null>(null);


  const fetchTips = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listTips({
        department: department === 'all' ? undefined : department,
        sort_by: sortBy,
        category: categoryFilter === 'all' ? undefined : categoryFilter,
      });
      setTips(result);
    } catch (err) {
      console.error('Failed to fetch tips:', err);
      setError('Failed to load tips. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [department, sortBy, categoryFilter]);

  useEffect(() => {
    fetchTips();
  }, [fetchTips]);

  const handleVote = useCallback(async (e: React.MouseEvent, tip: Tip) => {
    e.stopPropagation();
    const wasVoted = tip.user_has_voted;
    const newCount = wasVoted ? tip.vote_count - 1 : tip.vote_count + 1;
    setTips((prev) =>
      prev.map((t) =>
        t.tip_id === tip.tip_id
          ? { ...t, user_has_voted: !wasVoted, vote_count: newCount }
          : t
      )
    );
    try {
      if (wasVoted) {
        await unvoteTip(tip.tip_id);
      } else {
        await voteTip(tip.tip_id);
      }
    } catch {
      setTips((prev) =>
        prev.map((t) =>
          t.tip_id === tip.tip_id
            ? { ...t, user_has_voted: wasVoted, vote_count: tip.vote_count }
            : t
        )
      );
    }
  }, []);

  const handlePublished = useCallback(() => {
    setShowCreateForm(null);
    fetchTips();
  }, [fetchTips]);

  // Create gem/skill form
  if (showCreateForm) {
    return (
      <CreateGemSkillForm
        category={showCreateForm}
        onBack={() => setShowCreateForm(null)}
        onPublished={handlePublished}
      />
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Header */}
      <div className="px-4 md:px-6 pt-5 pb-3">
        <div className="flex items-start justify-between gap-4 mb-2">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Tips & Tricks
            </h1>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Share what you've learned with colleagues across the organization. Post general tips, Gemini Gems you've built, or Claude Skills that others can use.
            </p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={() => startTypedSession('tip')}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--color-surface-raised)]"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
            >
              <Plus className="w-3 h-3" strokeWidth={2} />
              Share a General Tip
            </button>
            <button
              onClick={() => setShowCreateForm('gem')}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--color-surface-raised)]"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
            >
              <GeminiIcon size={13} />
              Share a Gemini Gem
            </button>
            <button
              onClick={() => setShowCreateForm('skill')}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:bg-[var(--color-surface-raised)]"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)' }}
            >
              <ClaudeIcon size={13} />
              Share a Claude Skill
            </button>
          </div>
        </div>

        <div className="border-b my-3" style={{ borderColor: 'var(--color-border)' }} />

        {/* Category tabs + filters on same row */}
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {CATEGORY_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setCategoryFilter(tab.value)}
                className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full transition-colors duration-150"
                style={{
                  backgroundColor: categoryFilter === tab.value ? 'var(--color-primary-subtle)' : 'transparent',
                  color: categoryFilter === tab.value ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  fontWeight: categoryFilter === tab.value ? 500 : 400,
                }}
              >
                {tab.value === 'gem' && <GeminiIcon size={13} />}
                {tab.value === 'skill' && <ClaudeIcon size={13} />}
                {tab.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="text-sm rounded-lg border px-2.5 py-1.5 outline-none"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-secondary)',
                backgroundColor: 'var(--color-surface-white)',
              }}
            >
              <option value="all">All Departments</option>
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {formatDepartmentName(d)}
                </option>
              ))}
            </select>
            <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: 'var(--color-border)' }}>
              <button
                onClick={() => setSortBy('recent')}
                className="text-sm px-2.5 py-1.5 transition-colors duration-150"
                style={{
                  backgroundColor: sortBy === 'recent' ? 'var(--color-primary-subtle)' : 'var(--color-surface-white)',
                  color: sortBy === 'recent' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  fontWeight: sortBy === 'recent' ? 500 : 400,
                }}
              >
                Recent
              </button>
              <button
                onClick={() => setSortBy('popular')}
                className="text-sm px-2.5 py-1.5 transition-colors duration-150 border-l"
                style={{
                  borderColor: 'var(--color-border)',
                  backgroundColor: sortBy === 'popular' ? 'var(--color-primary-subtle)' : 'var(--color-surface-white)',
                  color: sortBy === 'popular' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  fontWeight: sortBy === 'popular' ? 500 : 400,
                }}
              >
                Popular
              </button>
            </div>
          </div>
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
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>{error}</p>
            <button
              onClick={fetchTips}
              className="text-sm font-medium px-3 py-1.5 rounded-lg"
              style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-subtle)' }}
            >
              Retry
            </button>
          </div>
        ) : tips.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-12 px-8 text-center max-w-md mx-auto mt-8 rounded-xl border"
            style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
          >
            {/* Icon cluster */}
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface-raised)' }}>
                <Lightbulb className="w-5 h-5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
              </div>
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface-raised)' }}>
                <GeminiIcon size={20} />
              </div>
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--color-surface-raised)' }}>
                <ClaudeIcon size={20} />
              </div>
            </div>

            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              {categoryFilter === 'all'
                ? 'This is where the good stuff lives'
                : categoryFilter === 'gem'
                  ? 'No Gemini Gems shared yet'
                  : categoryFilter === 'skill'
                    ? 'No Claude Skills shared yet'
                    : 'No general tips shared yet'}
            </h3>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {categoryFilter === 'all'
                ? 'When someone figures out a better way to do something with AI, this is where they share it. Tips, Gemini Gems, Claude Skills - all in one place.'
                : categoryFilter === 'gem'
                  ? 'Built a Gemini Gem that saves you time? Share it so others can use it too.'
                  : categoryFilter === 'skill'
                    ? 'Created a Claude Skill that works well? Share the definition so colleagues can try it.'
                    : 'Discovered a useful technique or workflow? Share what you learned so others can benefit.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3 max-w-2xl mx-auto">
            {tips.map((tip) => {
              const cat = tip.category || 'tip';
              const catColor = CATEGORY_COLORS[cat] || CATEGORY_COLORS.tip;
              return (
                <button
                  key={tip.tip_id}
                  onClick={() => navigate(`/tips/${tip.tip_id}`)}
                  className="w-full text-left rounded-xl border p-4 transition-all duration-200 hover:border-[var(--color-primary)] cursor-pointer"
                  style={{
                    backgroundColor: 'var(--color-surface-white)',
                    borderColor: 'var(--color-border)',
                  }}
                >
                  {/* Author + department + category */}
                  <div className="flex items-center gap-2 mb-2">
                    <ProfileChip userId={tip.author_id} avatarSize={20} />
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        backgroundColor: 'var(--color-surface-raised)',
                        color: 'var(--color-text-muted)',
                      }}
                    >
                      {formatDepartmentName(tip.department)}
                    </span>
                    <span
                      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
                      style={{
                        backgroundColor: catColor.bg,
                        color: catColor.text,
                      }}
                    >
                      {cat === 'gem' && <GeminiIcon size={11} />}
                      {cat === 'skill' && <ClaudeIcon size={11} />}
                      {CATEGORY_LABELS[cat] || 'General Tip'}
                    </span>
                  </div>

                  {/* Title */}
                  <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    {tip.title}
                  </p>

                  {/* Content summary */}
                  <p
                    className="text-sm mb-2"
                    style={{
                      color: 'var(--color-text-secondary)',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {tip.summary || stripMarkdown(tip.content)}
                  </p>

                  {/* Tags */}
                  {tip.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
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

                  {/* Bottom row: date + comments + upvote */}
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {relativeTime(tip.created_at)}
                    </span>
                    <div className="flex items-center gap-3">
                      {(tip.comment_count || 0) > 0 && (
                        <div className="flex items-center gap-1" style={{ color: 'var(--color-text-muted)' }}>
                          <MessageCircle className="w-3.5 h-3.5" strokeWidth={1.5} />
                          <span className="text-xs font-medium">{tip.comment_count}</span>
                        </div>
                      )}
                      <div
                        onClick={(e) => handleVote(e, tip)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleVote(e as any, tip); } }}
                        className="flex items-center gap-1.5 px-2 py-1 rounded-lg transition-colors duration-150"
                        style={{
                          backgroundColor: tip.user_has_voted ? 'var(--color-primary-subtle)' : 'transparent',
                          color: tip.user_has_voted ? 'var(--color-primary)' : 'var(--color-text-muted)',
                        }}
                        aria-label={tip.user_has_voted ? 'Remove upvote' : 'Upvote'}
                      >
                        <ThumbsUp
                          className="w-3.5 h-3.5"
                          strokeWidth={1.5}
                          fill={tip.user_has_voted ? 'currentColor' : 'none'}
                        />
                        <span className="text-xs font-medium">{tip.vote_count}</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
