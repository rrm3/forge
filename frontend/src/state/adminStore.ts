import { create } from 'zustand';

interface AdminState {
  isAdmin: boolean;
  isDepartmentAdmin: boolean;
  isReportViewer: boolean;
  adminMode: boolean;
  setAdminAccess: (isAdmin: boolean, isDepartmentAdmin: boolean, isReportViewer: boolean) => void;
  toggleAdminMode: () => void;
}

export const useAdminStore = create<AdminState>((set) => ({
  isAdmin: false,
  isDepartmentAdmin: false,
  isReportViewer: false,
  adminMode: localStorage.getItem('forge-admin-mode') === 'true',
  setAdminAccess: (isAdmin, isDepartmentAdmin, isReportViewer) =>
    set((s) => {
      if (!isAdmin && s.adminMode) {
        localStorage.removeItem('forge-admin-mode');
        return { isAdmin, isDepartmentAdmin, isReportViewer, adminMode: false };
      }
      return { isAdmin, isDepartmentAdmin, isReportViewer };
    }),
  toggleAdminMode: () =>
    set((s) => {
      const next = !s.adminMode;
      localStorage.setItem('forge-admin-mode', next ? 'true' : 'false');
      return { adminMode: next };
    }),
}));
