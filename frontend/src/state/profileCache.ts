import { create } from 'zustand';

export interface PublicProfile {
  user_id: string;
  name: string;
  title: string;
  department: string;
  avatar_url: string;
  team: string;
}

interface ProfileCacheState {
  profiles: Record<string, PublicProfile>;
  loading: Set<string>;
  set: (userId: string, profile: PublicProfile) => void;
  markLoading: (userId: string) => void;
}

export const useProfileCache = create<ProfileCacheState>((set) => ({
  profiles: {},
  loading: new Set(),
  set: (userId, profile) =>
    set((s) => ({
      profiles: { ...s.profiles, [userId]: profile },
      loading: (() => { const next = new Set(s.loading); next.delete(userId); return next; })(),
    })),
  markLoading: (userId) =>
    set((s) => ({ loading: new Set(s.loading).add(userId) })),
}));
