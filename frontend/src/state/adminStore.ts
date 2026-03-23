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
  setAdminAccess: (isAdmin, isDepartmentAdmin) =>
    set((s) => {
      // Clear adminMode if user is no longer a full admin (stale localStorage)
      if (!isAdmin && s.adminMode) {
        localStorage.removeItem('forge-admin-mode');
        return { isAdmin, isDepartmentAdmin, adminMode: false };
      }
      return { isAdmin, isDepartmentAdmin };
    }),
  toggleAdminMode: () =>
    set((s) => {
      const next = !s.adminMode;
      localStorage.setItem('forge-admin-mode', next ? 'true' : 'false');
      return { adminMode: next };
    }),
}));
