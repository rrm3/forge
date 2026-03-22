import { useCallback } from 'react';
import { ArrowLeft, ThumbsUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { voteTip, unvoteTip } from '../api/client';
import type { Tip } from '../api/types';

interface TipDetailProps {
  tip: Tip;
  onBack: () => void;
  onVoteChange: (tipId: string, voted: boolean, newCount: number) => void;
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

export function TipDetail({ tip, onBack, onVoteChange }: TipDetailProps) {
  const handleVote = useCallback(async () => {
    const wasVoted = tip.user_has_voted;
    const newCount = wasVoted ? tip.vote_count - 1 : tip.vote_count + 1;

    // Optimistic update
    onVoteChange(tip.tip_id, !wasVoted, newCount);

    try {
      if (wasVoted) {
        await unvoteTip(tip.tip_id);
      } else {
        await voteTip(tip.tip_id);
      }
    } catch {
      // Revert on failure
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

          {/* Title */}
          <h1 className="text-2xl font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
            {tip.title}
          </h1>

          {/* Author, department, date */}
          <div className="flex flex-wrap items-center gap-2 mb-5">
            <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {tip.author_name}
            </span>
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
        </div>
      </div>
    </div>
  );
}
