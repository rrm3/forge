/**
 * AdminLayout - Shared chrome for admin sub-pages.
 * Renders a back link, tab nav (Settings | Users), and child route via Outlet.
 */

import { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useAdminStore } from '../state/adminStore';

type Tab = 'settings' | 'company' | 'users' | 'reports';

export function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const isAdmin = useAdminStore((s) => s.isAdmin);
  const isDepartmentAdmin = useAdminStore((s) => s.isDepartmentAdmin);
  const isReportViewer = useAdminStore((s) => s.isReportViewer);
  const reportViewerOnly = isReportViewer && !isAdmin && !isDepartmentAdmin;

  const activeTab: Tab = location.pathname.includes('/admin/reports')
    ? 'reports'
    : location.pathname.includes('/admin/users')
      ? 'users'
      : location.pathname.includes('/admin/company')
        ? 'company'
        : 'settings';

  // Mobile gate
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    function handleResize() {
      setIsMobile(window.innerWidth < 768);
    }
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (isMobile) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full px-6 text-center"
        style={{ backgroundColor: 'var(--color-surface)' }}
      >
        <p
          className="text-sm mb-4"
          style={{ color: 'var(--color-text-secondary)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
        >
          Please use a desktop browser to access admin settings.
        </p>
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm font-medium"
          style={{ color: 'var(--color-text-muted)', cursor: 'pointer' }}
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to AI Tuesdays
        </button>
      </div>
    );
  }

  const tabStyle = (tab: Tab) => ({
    fontSize: 14,
    fontWeight: 500 as const,
    fontFamily: "'Satoshi', system-ui, sans-serif",
    color: activeTab === tab ? 'var(--color-primary)' : 'var(--color-text-muted)',
    borderBottom: activeTab === tab ? '2px solid var(--color-primary)' : '2px solid transparent',
    cursor: 'pointer' as const,
    paddingBottom: 8,
    background: 'none',
    border: 'none',
  });

  return (
    <div
      className="flex-1 overflow-y-auto"
      style={{ backgroundColor: 'var(--color-surface)' }}
    >
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Back link */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-1.5 text-sm font-medium mb-6 transition-colors"
          style={{ color: 'var(--color-text-muted)', cursor: 'pointer' }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-primary)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-text-muted)'; }}
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          Back to AI Tuesdays
        </button>

        {/* Page heading */}
        <h1
          className="text-2xl font-semibold mb-1"
          style={{
            color: 'var(--color-text-primary)',
            fontFamily: "'Satoshi', system-ui, sans-serif",
          }}
        >
          Admin
        </h1>

        {/* Tab nav - Company Context and Users tabs only visible to full admins.
            Report-viewer-only users see just the Reports tab. */}
        <div className="flex gap-6 mb-6 mt-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
          {!reportViewerOnly && (
            <button onClick={() => navigate('/admin/settings')} style={tabStyle('settings')}>
              Questions
            </button>
          )}
          {isAdmin && (
            <button onClick={() => navigate('/admin/company')} style={tabStyle('company')}>
              System Prompts
            </button>
          )}
          {isAdmin && (
            <button onClick={() => navigate('/admin/users')} style={tabStyle('users')}>
              Users
            </button>
          )}
          {(isAdmin || isReportViewer) && (
            <button onClick={() => navigate('/admin/reports')} style={tabStyle('reports')}>
              Reports
            </button>
          )}
        </div>

        {/* Child route content */}
        <Outlet />
      </div>
    </div>
  );
}
