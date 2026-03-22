import { useEffect } from 'react';
import { useProfileCache } from '../state/profileCache';
import { getPublicProfile } from '../api/client';
import { UserAvatar } from './UserAvatar';

interface ProfileChipProps {
  userId: string;
  showName?: boolean;
  avatarSize?: number;
}

export function ProfileChip({ userId, showName = true, avatarSize = 24 }: ProfileChipProps) {
  const profile = useProfileCache((s) => s.profiles[userId]);
  const isLoading = useProfileCache((s) => s.loading.has(userId));
  const { set, markLoading } = useProfileCache();

  useEffect(() => {
    // Use getState() to avoid race where multiple chips for the same user
    // all see isLoading=false in the same render tick
    const state = useProfileCache.getState();
    if (state.profiles[userId] || state.loading.has(userId)) return;
    markLoading(userId);
    getPublicProfile(userId)
      .then((p) => set(userId, p))
      .catch(() => {
        set(userId, { user_id: userId, name: 'Unknown', title: '', department: '', avatar_url: '', team: '' });
      });
  }, [userId, profile, isLoading, set, markLoading]);

  if (!profile) {
    return (
      <div className="flex items-center gap-1.5">
        <div
          className="rounded-full shrink-0 animate-pulse"
          style={{ width: avatarSize, height: avatarSize, backgroundColor: 'var(--color-surface-raised)' }}
        />
        {showName && (
          <span
            className="rounded animate-pulse"
            style={{ width: 60, height: 12, backgroundColor: 'var(--color-surface-raised)', display: 'inline-block' }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <UserAvatar
        name={profile.name}
        avatarUrl={profile.avatar_url}
        title={profile.title}
        department={profile.department}
        size={avatarSize}
      />
      {showName && (
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          {profile.name}
        </span>
      )}
    </div>
  );
}
