import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ThumbsUp } from 'lucide-react';
import { listTips, getTip, voteTip, unvoteTip } from '../api/client';
import type { Tip } from '../api/types';
import { TipDetail } from './TipDetail';
import { ProfileChip } from './ProfileChip';

interface TipsViewProps {
  userDepartment?: string;
  initialTipId?: string;
}

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

function formatDepartmentName(slug: string): string {
  return slug
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/** Strip markdown syntax for plain-text card previews. */
function stripMarkdown(md: string): string {
  return md
    .replace(/^#{1,6}\s+/gm, '')        // headings
    .replace(/\*\*(.+?)\*\*/g, '$1')    // bold
    .replace(/\*(.+?)\*/g, '$1')        // italic
    .replace(/`(.+?)`/g, '$1')          // inline code
    .replace(/^\s*[-*+]\s+/gm, '')      // list bullets
    .replace(/^\s*\d+\.\s+/gm, '')      // numbered lists
    .replace(/\[(.+?)\]\(.+?\)/g, '$1') // links
    .replace(/\n{2,}/g, ' ')            // collapse double newlines
    .replace(/\n/g, ' ')                // remaining newlines
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

export function TipsView({ userDepartment, initialTipId }: TipsViewProps) {
  const navigate = useNavigate();
  const [tips, setTips] = useState<Tip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [department, setDepartment] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'recent' | 'popular'>('recent');
  const [selectedTip, setSelectedTip] = useState<Tip | null>(null);

  // Load a specific tip when navigating directly to /tips/:tipId
  useEffect(() => {
    if (initialTipId && !selectedTip) {
      getTip(initialTipId)
        .then((tip) => setSelectedTip(tip))
        .catch(() => navigate('/tips', { replace: true }));
    }
  }, [initialTipId, selectedTip, navigate]);

  const fetchTips = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listTips({
        department: department === 'all' ? undefined : department,
        sort_by: sortBy,
      });
      setTips(result);
    } catch (err) {
      console.error('Failed to fetch tips:', err);
      setError('Failed to load tips. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [department, sortBy]);

  useEffect(() => {
    fetchTips();
  }, [fetchTips]);

  const handleVote = useCallback(async (e: React.MouseEvent, tip: Tip) => {
    e.stopPropagation();
    const wasVoted = tip.user_has_voted;
    const newCount = wasVoted ? tip.vote_count - 1 : tip.vote_count + 1;

    // Optimistic update
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
      // Revert on failure
      setTips((prev) =>
        prev.map((t) =>
          t.tip_id === tip.tip_id
            ? { ...t, user_has_voted: wasVoted, vote_count: tip.vote_count }
            : t
        )
      );
    }
  }, []);

  const handleVoteChange = useCallback((tipId: string, voted: boolean, newCount: number) => {
    setTips((prev) =>
      prev.map((t) =>
        t.tip_id === tipId
          ? { ...t, user_has_voted: voted, vote_count: newCount }
          : t
      )
    );
  }, []);

  const handleTipUpdated = useCallback((updated: Tip) => {
    setTips((prev) => prev.map((t) => t.tip_id === updated.tip_id ? updated : t));
    setSelectedTip(updated);
  }, []);

  const handleTipDeleted = useCallback((tipId: string) => {
    setTips((prev) => prev.filter((t) => t.tip_id !== tipId));
    setSelectedTip(null);
  }, []);

  if (selectedTip) {
    return (
      <TipDetail
        tip={selectedTip}
        onBack={() => { setSelectedTip(null); fetchTips(); navigate('/tips'); }}
        onVoteChange={handleVoteChange}
        onTipUpdated={handleTipUpdated}
        onTipDeleted={handleTipDeleted}
      />
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Header */}
      <div className="px-4 md:px-6 pt-5 pb-4">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => navigate('/')}
            className="flex items-center justify-center w-8 h-8 rounded-lg transition-colors duration-150 hover:bg-[var(--color-surface-raised)]"
            aria-label="Go back"
          >
            <ArrowLeft className="w-5 h-5" style={{ color: 'var(--color-text-secondary)' }} strokeWidth={1.5} />
          </button>
          <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Tips & Tricks
          </h1>
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-3">
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
              className="text-sm px-3 py-1.5 transition-colors duration-150"
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
              className="text-sm px-3 py-1.5 transition-colors duration-150 border-l"
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
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              No tips yet. Be the first to share what you've learned!
            </p>
          </div>
        ) : (
          <div className="space-y-3 max-w-2xl mx-auto">
            {tips.map((tip) => (
              <button
                key={tip.tip_id}
                onClick={() => { setSelectedTip(tip); navigate(`/tips/${tip.tip_id}`); }}
                className="w-full text-left rounded-xl border p-4 transition-all duration-200 hover:border-[var(--color-primary)]"
                style={{
                  backgroundColor: 'var(--color-surface-white)',
                  borderColor: 'var(--color-border)',
                }}
              >
                {/* Author + department */}
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

                {/* Bottom row: date + upvote */}
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {relativeTime(tip.created_at)}
                  </span>
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
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
