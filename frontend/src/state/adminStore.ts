import { create } from 'zustand';

interface AdminState {
  isAdmin: boolean;
  adminMode: boolean;
  setIsAdmin: (v: boolean) => void;
  toggleAdminMode: () => void;
}

export const useAdminStore = create<AdminState>((set) => ({
  isAdmin: false,
  adminMode: localStorage.getItem('forge-admin-mode') === 'true',
  setIsAdmin: (v) => set({ isAdmin: v }),
  toggleAdminMode: () =>
    set((s) => {
      const next = !s.adminMode;
      localStorage.setItem('forge-admin-mode', next ? 'true' : 'false');
      return { adminMode: next };
    }),
}));
