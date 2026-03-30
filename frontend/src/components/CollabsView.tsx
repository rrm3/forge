import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Users } from 'lucide-react';
import { listCollabs } from '../api/client';
import type { Collaboration, CollabStatus } from '../api/types';
import { ProfileChip } from './ProfileChip';
import { useAuth } from '../auth/useAuth';
import { useSession } from '../state/SessionContext';

type StatusFilter = 'all' | CollabStatus | 'mine';

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'building', label: 'Building' },
  { value: 'done', label: 'Done' },
  { value: 'mine', label: 'My Collabs' },
];

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

function InterestedCount({ count }: { count: number }) {
  if (count === 0) return null;

  return (
    <div className="flex items-center gap-1.5">
      <Users className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
        {count} interested
      </span>
    </div>
  );
}

export function CollabsView() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { startTypedSession } = useSession();
  const [collabs, setCollabs] = useState<Collaboration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const fetchCollabs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { status?: string } = {};
      if (statusFilter !== 'all' && statusFilter !== 'mine') {
        params.status = statusFilter;
      }
      const result = await listCollabs(params);
      setCollabs(result);
    } catch (err) {
      console.error('Failed to fetch collabs:', err);
      setError('Failed to load collabs. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchCollabs();
  }, [fetchCollabs]);

  const filtered = statusFilter === 'mine'
    ? collabs.filter((c) => c.author_id === user?.userId)
    : collabs;

  return (
    <div className="flex flex-col h-full" style={{ backgroundColor: 'var(--color-surface-white)' }}>
      {/* Header */}
      <div className="px-4 md:px-6 pt-5 pb-3">
        <div className="flex items-start justify-between gap-4 mb-2">
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
              Collabs
            </h1>
            <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              Find collaborators for projects across Digital Science. Post an idea, gather interest, and build together.
            </p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button
              onClick={() => startTypedSession('collab')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition-colors"
              style={{ backgroundColor: 'var(--color-primary)' }}
            >
              <Plus className="w-3.5 h-3.5" strokeWidth={2} />
              Start a Collab
            </button>
          </div>
        </div>

        <div className="border-b my-3" style={{ borderColor: 'var(--color-border)' }} />

        {/* Status tabs */}
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setStatusFilter(tab.value)}
                className="text-sm px-3 py-1.5 rounded-full transition-colors duration-150"
                style={{
                  backgroundColor: statusFilter === tab.value ? 'var(--color-primary-subtle)' : 'transparent',
                  color: statusFilter === tab.value ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  fontWeight: statusFilter === tab.value ? 500 : 400,
                }}
              >
                {tab.label}
              </button>
            ))}
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
              onClick={fetchCollabs}
              className="text-sm font-medium px-3 py-1.5 rounded-lg"
              style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-subtle)' }}
            >
              Retry
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-12 px-8 text-center max-w-md mx-auto mt-8 rounded-xl border"
            style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
          >
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-5" style={{ backgroundColor: 'var(--color-surface-raised)' }}>
              <Users className="w-6 h-6" style={{ color: 'var(--color-text-muted)' }} strokeWidth={1.5} />
            </div>
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
              Got an idea that needs a partner?
            </h3>
            <p className="text-sm mb-5" style={{ color: 'var(--color-text-secondary)' }}>
              Post a project you'd like to collaborate on. Colleagues across Digital Science can express interest, and you can connect to make it happen.
            </p>
            <button
              onClick={() => startTypedSession('collab')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
              style={{ backgroundColor: 'var(--color-primary)' }}
            >
              <Plus className="w-3.5 h-3.5" strokeWidth={2} />
              Start a Collab
            </button>
          </div>
        ) : (
          <div className="space-y-3 max-w-2xl mx-auto">
            {filtered.map((collab) => (
              <button
                key={collab.collab_id}
                onClick={() => navigate(`/collabs/${collab.collab_id}`)}
                className="w-full text-left rounded-xl border p-4 transition-all duration-200 hover:border-[var(--color-primary)] cursor-pointer"
                style={{
                  backgroundColor: 'var(--color-surface-white)',
                  borderColor: 'var(--color-border)',
                }}
              >
                {/* Row 1: Author + dept + status */}
                <div className="flex items-center gap-2 mb-2">
                  <ProfileChip userId={collab.author_id} avatarSize={20} />
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
                </div>

                {/* Row 2: Title */}
                <p className="text-sm font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  {collab.title}
                </p>

                {/* Row 3: Problem (2-line clamp) */}
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
                  {collab.problem}
                </p>

                {/* Row 4: Needed skills */}
                {collab.needed_skills.length > 0 && (
                  <div className="flex items-center flex-wrap gap-1.5 mb-2">
                    <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Needs:</span>
                    {collab.needed_skills.map((skill) => (
                      <span
                        key={skill}
                        className="text-xs px-2 py-0.5 rounded-full"
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

                {/* Row 5: Timestamp + interested */}
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {relativeTime(collab.created_at)}
                  </span>
                  <InterestedCount count={collab.interested_count} />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
