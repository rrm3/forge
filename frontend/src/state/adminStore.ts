import { create } from 'zustand';

interface AdminState {
  isAdmin: boolean;
  isDepartmentAdmin: boolean;
  adminMode: boolean;
  setAdminAccess: (isAdmin: boolean, isDepartmentAdmin: boolean) => void;
  toggleAdminMode: () => void;
}

export const useAdminStore = create<AdminState>((set) => ({
  isAdmin: false,
  isDepartmentAdmin: false,
  adminMode: localStorage.getItem('forge-admin-mode') === 'true',
  setAdminAccess: (isAdmin, isDepartmentAdmin) => set({ isAdmin, isDepartmentAdmin }),
  toggleAdminMode: () =>
    set((s) => {
      const next = !s.adminMode;
      localStorage.setItem('forge-admin-mode', next ? 'true' : 'false');
      return { adminMode: next };
    }),
}));
