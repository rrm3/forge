/**
 * AdminUsers - User dashboard showing all users with stats and intake detail drill-down.
 */

import { useEffect, useState, useMemo } from 'react';
import { Search, X, ChevronUp, ChevronDown, Shield } from 'lucide-react';
import { listAdminUsers, getAdminUserIntake, setUserRole, setUserAdmin, deleteAdminUser } from '../api/client';
import { UserAvatar } from './UserAvatar';
import { getProgramWeek } from '../program';
import type { AdminUserSummary, AdminUserIntake } from '../api/types';

type SortKey = 'name' | 'department' | 'role' | 'session_count' | 'tip_count' | 'intake' | 'last_active';
type SortDir = 'asc' | 'desc';

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never';
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// Intake response display labels
const INTAKE_LABELS: Record<string, string> = {
  products: 'Products Used',
  daily_tasks: 'Daily Tasks',
  core_skills: 'Core Skills',
  learning_goals: 'Learning Goals',
  ai_tools_used: 'AI Tools Used',
  ai_superpower: 'AI Superpower',
  work_summary: 'Work Summary',
};

function formatIntakeValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object' && value !== null) {
    // Handle nested objects like {value: "...", captured_at: "..."}
    const v = (value as Record<string, unknown>).value;
    if (typeof v === 'string') {
      if (v === 'answered') return 'Captured, processing...';
      return v;
    }
    return JSON.stringify(value);
  }
  if (value === 'answered') return 'Captured, processing...';
  return String(value ?? '');
}

export function AdminUsers() {
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  // Detail panel
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [intakeDetail, setIntakeDetail] = useState<AdminUserIntake | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function handleToggleRole(userId: string, isDeptAdmin: boolean) {
    try {
      await setUserRole(userId, isDeptAdmin);
      setUsers((prev) =>
        prev.map((u) => u.user_id === userId ? { ...u, is_department_admin: isDeptAdmin } : u)
      );
    } catch (err) {
      console.error('Failed to update role:', err);
    }
  }

  async function handleToggleAdmin(userId: string, isAdmin: boolean) {
    try {
      await setUserAdmin(userId, isAdmin);
      setUsers((prev) =>
        prev.map((u) => u.user_id === userId ? { ...u, is_admin: isAdmin } : u)
      );
    } catch (err) {
      console.error('Failed to update admin status:', err);
    }
  }

  async function handleDeleteUser(userId: string) {
    try {
      await deleteAdminUser(userId);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
      setSelectedUserId(null);
    } catch (err) {
      console.error('Failed to delete user:', err);
      alert('Failed to delete user. Check the console for details.');
    }
  }

  useEffect(() => {
    listAdminUsers()
      .then((u) => { setUsers(u); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // Load intake detail when a user is selected
  useEffect(() => {
    if (!selectedUserId) {
      setIntakeDetail(null);
      return;
    }
    setDetailLoading(true);
    getAdminUserIntake(selectedUserId)
      .then((d) => { setIntakeDetail(d); setDetailLoading(false); })
      .catch(() => setDetailLoading(false));
  }, [selectedUserId]);

  // Unique departments for filter
  const departments = useMemo(() => {
    const depts = new Set(users.map((u) => u.department).filter(Boolean));
    return [...depts].sort();
  }, [users]);

  // Filter and sort
  const filtered = useMemo(() => {
    let result = users;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)
      );
    }
    if (deptFilter) {
      result = result.filter((u) => u.department === deptFilter);
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'name':
          cmp = a.name.localeCompare(b.name);
          break;
        case 'department':
          cmp = a.department.localeCompare(b.department);
          break;
        case 'role': {
          const roleWeight = (u: AdminUserSummary) => (u.is_admin ? 2 : 0) + (u.is_department_admin ? 1 : 0);
          cmp = roleWeight(a) - roleWeight(b);
          break;
        }
        case 'session_count':
          cmp = a.session_count - b.session_count;
          break;
        case 'tip_count':
          cmp = a.tip_count - b.tip_count;
          break;
        case 'intake': {
          const pctA = a.intake_objectives_total > 0 ? a.intake_objectives_done / a.intake_objectives_total : (a.intake_completed_at ? 1 : -1);
          const pctB = b.intake_objectives_total > 0 ? b.intake_objectives_done / b.intake_objectives_total : (b.intake_completed_at ? 1 : -1);
          cmp = pctA - pctB;
        }
          break;
        case 'last_active':
          cmp = (a.last_active ?? '').localeCompare(b.last_active ?? '');
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return result;
  }, [users, search, deptFilter, sortKey, sortDir]);

  // Stats
  const totalUsers = users.length;
  const currentWeek = getProgramWeek();
  const weekStats = Array.from({ length: currentWeek }, (_, i) => {
    const w = i + 1;
    const complete = users.filter((u) => String(w) in (u.intake_weeks ?? {})).length;
    const pct = totalUsers > 0 ? Math.round((complete / totalUsers) * 100) : 0;
    return { week: w, complete, pct };
  });

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null;
    return sortDir === 'asc'
      ? <ChevronUp className="w-3 h-3 inline ml-0.5" strokeWidth={2} />
      : <ChevronDown className="w-3 h-3 inline ml-0.5" strokeWidth={2} />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div
          className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--color-primary)' }}
        />
      </div>
    );
  }

  const thStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 500,
    fontFamily: "'Satoshi', system-ui, sans-serif",
    color: 'var(--color-text-muted)',
    textAlign: 'left',
    padding: '10px 12px',
    cursor: 'pointer',
    userSelect: 'none',
    whiteSpace: 'nowrap',
  };

  const tdStyle: React.CSSProperties = {
    fontSize: 14,
    fontFamily: "'Satoshi', system-ui, sans-serif",
    color: 'var(--color-text-primary)',
    padding: '10px 12px',
    borderTop: '1px solid var(--color-border)',
  };

  const monoTd: React.CSSProperties = {
    ...tdStyle,
    fontFamily: "'Geist Mono', monospace",
    fontSize: 13,
  };

  return (
    <div className="relative">
      {/* Stats bar */}
      <div className={`grid gap-4 mb-6`} style={{ gridTemplateColumns: `repeat(${1 + weekStats.length}, 1fr)` }}>
        {[
          { label: 'Total Users', value: totalUsers },
          ...weekStats.map((s) => ({
            label: `Day ${s.week} Complete`,
            value: `${s.complete}/${totalUsers} (${s.pct}%)`,
          })),
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-lg border px-4 py-3"
            style={{ backgroundColor: '#FFFFFF', borderColor: 'var(--color-border)' }}
          >
            <div
              className="text-xs font-medium mb-1"
              style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
            >
              {stat.label}
            </div>
            <div
              className="text-xl font-semibold"
              style={{
                color: 'var(--color-text-primary)',
                fontFamily: "'Geist Mono', monospace",
              }}
            >
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Search and filter */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ width: 16, height: 16, color: 'var(--color-text-placeholder)' }}
            strokeWidth={1.5}
          />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border pl-9 pr-3 py-2 text-sm outline-none transition-colors"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-primary)',
              fontFamily: "'Satoshi', system-ui, sans-serif",
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary)'; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; }}
          />
        </div>
        <select
          value={deptFilter}
          onChange={(e) => setDeptFilter(e.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
          style={{
            borderColor: 'var(--color-border)',
            color: 'var(--color-text-primary)',
            fontFamily: "'Satoshi', system-ui, sans-serif",
            cursor: 'pointer',
          }}
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </div>

      {/* User table */}
      <div
        className="rounded-lg border overflow-hidden"
        style={{ backgroundColor: '#FFFFFF', borderColor: 'var(--color-border)' }}
      >
        <table className="w-full" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--color-surface)' }}>
              <th style={thStyle} onClick={() => handleSort('name')}>
                Name <SortIcon col="name" />
              </th>
              <th style={thStyle} onClick={() => handleSort('department')}>
                Department <SortIcon col="department" />
              </th>
              <th style={{ ...thStyle, textAlign: 'center' }} onClick={() => handleSort('role')}>
                Role <SortIcon col="role" />
              </th>
              <th style={{ ...thStyle, textAlign: 'center' }} onClick={() => handleSort('session_count')}>
                Sessions <SortIcon col="session_count" />
              </th>
              <th style={{ ...thStyle, textAlign: 'center' }} onClick={() => handleSort('tip_count')}>
                Tips <SortIcon col="tip_count" />
              </th>
              {weekStats.map((s, i) => (
                <th key={s.week} style={{ ...thStyle, textAlign: 'center' }} onClick={i === 0 ? () => handleSort('intake') : undefined}>
                  Day {s.week} {i === 0 && <SortIcon col="intake" />}
                </th>
              ))}
              <th style={thStyle} onClick={() => handleSort('last_active')}>
                Last Active <SortIcon col="last_active" />
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={6 + weekStats.length}
                  className="text-center py-8 text-sm"
                  style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
                >
                  No users found
                </td>
              </tr>
            ) : (
              filtered.map((u) => (
                <tr
                  key={u.user_id}
                  onClick={() => setSelectedUserId(u.user_id === selectedUserId ? null : u.user_id)}
                  className="transition-colors"
                  style={{
                    cursor: 'pointer',
                    backgroundColor: u.user_id === selectedUserId ? 'var(--color-primary-subtle, #E8F4F8)' : undefined,
                  }}
                  onMouseEnter={(e) => {
                    if (u.user_id !== selectedUserId) e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)';
                  }}
                  onMouseLeave={(e) => {
                    if (u.user_id !== selectedUserId) e.currentTarget.style.backgroundColor = '';
                  }}
                >
                  <td style={tdStyle}>
                    <div className="flex items-center gap-2.5">
                      <UserAvatar name={u.name} avatarUrl={u.avatar_url} size={28} />
                      <div>
                        <div className="font-medium text-sm" style={{ color: 'var(--color-text-primary)' }}>
                          {u.name || u.email}
                        </div>
                        {u.title && (
                          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                            {u.title}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td style={{ ...tdStyle, fontSize: 13 }}>
                    {u.department || '-'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <div className="flex items-center justify-center gap-1.5 flex-wrap">
                      {u.is_admin && (
                        <span
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            fontFamily: "'Satoshi', system-ui, sans-serif",
                            backgroundColor: '#FEF3C7',
                            color: '#B45309',
                          }}
                        >
                          <Shield className="w-3 h-3" strokeWidth={2} />
                          Admin
                        </span>
                      )}
                      {u.is_department_admin && (
                        <span
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5"
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            fontFamily: "'Satoshi', system-ui, sans-serif",
                            backgroundColor: '#EFF6FF',
                            color: '#2563EB',
                          }}
                        >
                          <Shield className="w-3 h-3" strokeWidth={2} />
                          Dept Admin
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{ ...monoTd, textAlign: 'center' }}>
                    {u.session_count}
                  </td>
                  <td style={{ ...monoTd, textAlign: 'center' }}>
                    {u.tip_count}
                  </td>
                  {weekStats.map((s) => (
                    <td key={s.week} style={{ ...monoTd, textAlign: 'center' }}>
                      {String(s.week) in (u.intake_weeks ?? {})
                        ? <span style={{ color: 'var(--color-success, #16A34A)' }}>&#10003;</span>
                        : s.week === currentWeek && u.intake_objectives_total > 0
                          ? <span style={{ color: 'var(--color-text-muted)', fontSize: 11 }}>{u.intake_objectives_done}/{u.intake_objectives_total}</span>
                          : <span style={{ color: 'var(--color-text-placeholder)' }}>--</span>}
                    </td>
                  ))}
                  <td style={{ ...tdStyle, fontSize: 13, color: 'var(--color-text-muted)' }}>
                    {relativeTime(u.last_active)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div
        className="text-xs mt-3"
        style={{ color: 'var(--color-text-placeholder)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
      >
        {filtered.length} of {totalUsers} users
      </div>

      {/* Detail slide-out panel */}
      {selectedUserId && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30"
            style={{ backgroundColor: 'rgba(0,0,0,0.15)' }}
            onClick={() => setSelectedUserId(null)}
          />
          {/* Panel */}
          <div
            className="fixed top-0 right-0 h-full z-40 overflow-y-auto"
            style={{
              width: 480,
              backgroundColor: '#FFFFFF',
              borderLeft: '1px solid var(--color-border)',
              boxShadow: '-8px 0 24px rgba(0,0,0,0.08)',
            }}
          >
            <DetailPanel
              userId={selectedUserId}
              user={users.find((u) => u.user_id === selectedUserId) ?? null}
              intake={intakeDetail}
              loading={detailLoading}
              currentWeek={currentWeek}
              onClose={() => setSelectedUserId(null)}
              onToggleRole={handleToggleRole}
              onToggleAdmin={handleToggleAdmin}
              onDelete={handleDeleteUser}
            />
          </div>
        </>
      )}
    </div>
  );
}

function DetailPanel({
  userId,
  user,
  intake,
  loading,
  currentWeek,
  onClose,
  onToggleRole,
  onToggleAdmin,
  onDelete,
}: {
  userId: string;
  user: AdminUserSummary | null;
  intake: AdminUserIntake | null;
  loading: boolean;
  currentWeek: number;
  onClose: () => void;
  onToggleRole: (userId: string, isDeptAdmin: boolean) => void;
  onToggleAdmin: (userId: string, isAdmin: boolean) => void;
  onDelete: (userId: string) => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  if (loading || !intake) {
    return (
      <div className="flex items-center justify-center h-64">
        <div
          className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--color-primary)' }}
        />
      </div>
    );
  }

  const p = intake.profile;

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <UserAvatar name={p.name} avatarUrl={p.avatar_url} size={48} />
          <div>
            <div
              className="text-lg font-semibold"
              style={{ color: 'var(--color-text-primary)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
            >
              {p.name}
            </div>
            <div className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {[p.title, p.department].filter(Boolean).join(' \u00b7 ')}
            </div>
            {p.team && (
              <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                {p.team}
              </div>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md transition-colors"
          style={{ color: 'var(--color-text-muted)', cursor: 'pointer' }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = ''; }}
        >
          <X className="w-5 h-5" strokeWidth={1.5} />
        </button>
      </div>

      {/* Role toggles */}
      {user && (
        <Section title="Role">
          {/* Admin toggle */}
          <button
            onClick={() => onToggleAdmin(userId, !user.is_admin)}
            className="flex items-center justify-between w-full rounded-lg border px-3 py-2.5 transition-colors"
            style={{
              borderColor: user.is_admin ? '#FDE68A' : 'var(--color-border)',
              backgroundColor: user.is_admin ? '#FFFBEB' : 'transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { if (!user.is_admin) e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)'; }}
            onMouseLeave={(e) => { if (!user.is_admin) e.currentTarget.style.backgroundColor = user.is_admin ? '#FFFBEB' : 'transparent'; }}
          >
            <span className="flex items-center gap-2">
              <Shield
                className="w-4 h-4"
                strokeWidth={1.5}
                style={{ color: user.is_admin ? '#B45309' : 'var(--color-text-muted)' }}
              />
              <span
                className="text-sm font-medium"
                style={{ color: user.is_admin ? '#B45309' : 'var(--color-text-primary)' }}
              >
                Admin
              </span>
            </span>
            <span
              className="relative inline-block rounded-full transition-colors"
              style={{
                width: 32,
                height: 18,
                backgroundColor: user.is_admin ? '#D97706' : '#CBD5E1',
              }}
            >
              <span
                className="absolute top-0.5 rounded-full bg-white transition-all shadow-sm"
                style={{
                  width: 14,
                  height: 14,
                  left: user.is_admin ? 16 : 2,
                }}
              />
            </span>
          </button>
          {user.is_admin && (
            <p className="text-xs mt-1.5 mb-3" style={{ color: 'var(--color-text-muted)' }}>
              Full admin access: can manage all departments and users
            </p>
          )}
          {!user.is_admin && <div className="mb-3" />}

          {/* Department Admin toggle */}
          <button
            onClick={() => onToggleRole(userId, !user.is_department_admin)}
            className="flex items-center justify-between w-full rounded-lg border px-3 py-2.5 transition-colors"
            style={{
              borderColor: user.is_department_admin ? '#BFDBFE' : 'var(--color-border)',
              backgroundColor: user.is_department_admin ? '#EFF6FF' : 'transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { if (!user.is_department_admin) e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)'; }}
            onMouseLeave={(e) => { if (!user.is_department_admin) e.currentTarget.style.backgroundColor = user.is_department_admin ? '#EFF6FF' : 'transparent'; }}
          >
            <span className="flex items-center gap-2">
              <Shield
                className="w-4 h-4"
                strokeWidth={1.5}
                style={{ color: user.is_department_admin ? '#2563EB' : 'var(--color-text-muted)' }}
              />
              <span
                className="text-sm font-medium"
                style={{ color: user.is_department_admin ? '#2563EB' : 'var(--color-text-primary)' }}
              >
                Department Admin
              </span>
            </span>
            <span
              className="relative inline-block rounded-full transition-colors"
              style={{
                width: 32,
                height: 18,
                backgroundColor: user.is_department_admin ? '#2563EB' : '#CBD5E1',
              }}
            >
              <span
                className="absolute top-0.5 rounded-full bg-white transition-all shadow-sm"
                style={{
                  width: 14,
                  height: 14,
                  left: user.is_department_admin ? 16 : 2,
                }}
              />
            </span>
          </button>
          {user.is_department_admin && (
            <p className="text-xs mt-1.5" style={{ color: 'var(--color-text-muted)' }}>
              Can view and edit department settings for {p.department || 'their department'}
            </p>
          )}
        </Section>
      )}

      {/* Intake Summary */}
      {p.intake_summary && (
        <Section title="Intake Summary">
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
            {p.intake_summary}
          </p>
        </Section>
      )}

      {/* Profile fields from intake */}
      <Section title="Profile Details">
        <div className="flex flex-col gap-3">
          {p.products && p.products.length > 0 && (
            <Field label="Products" value={p.products.join(', ')} />
          )}
          {p.daily_tasks && <Field label="Daily Tasks" value={p.daily_tasks} />}
          {p.core_skills && p.core_skills.length > 0 && (
            <Field label="Core Skills" value={p.core_skills.join(', ')} />
          )}
          {p.learning_goals && p.learning_goals.length > 0 && (
            <Field label="Learning Goals" value={p.learning_goals.join(', ')} />
          )}
          {p.ai_tools_used && p.ai_tools_used.length > 0 && (
            <Field label="AI Tools Used" value={p.ai_tools_used.join(', ')} />
          )}
          {p.ai_superpower && <Field label="AI Superpower" value={p.ai_superpower} />}
          {p.work_summary && <Field label="Work Summary" value={p.work_summary} />}
        </div>
      </Section>

      {/* Raw intake responses (from objectives extraction) */}
      {intake.intake_responses && Object.keys(intake.intake_responses).length > 0 && (
        <Section title="Intake Responses">
          <div className="flex flex-col gap-3">
            {Object.entries(intake.intake_responses).map(([key, value]) => (
              <Field
                key={key}
                label={INTAKE_LABELS[key] || key.replace(/_/g, ' ')}
                value={formatIntakeValue(value)}
              />
            ))}
          </div>
        </Section>
      )}

      {/* Intake status */}
      <Section title="Status">
        <div className="flex flex-col gap-2 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          {Array.from({ length: currentWeek }, (_, i) => i + 1).map((week) => {
            const weekStr = String(week);
            const completed = weekStr in (p.intake_weeks ?? {});
            const completedAt = completed ? (p.intake_weeks ?? {})[weekStr] : null;
            return (
              <div key={week} className="flex justify-between">
                <span>Day {week}</span>
                <span style={{ fontFamily: "'Geist Mono', monospace", fontSize: 13 }}>
                  {completedAt
                    ? new Date(completedAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
                    : 'Not started'}
                </span>
              </div>
            );
          })}
          <div className="flex justify-between">
            <span>Account created</span>
            <span style={{ fontFamily: "'Geist Mono', monospace", fontSize: 13 }}>
              {new Date(p.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Email</span>
            <span style={{ fontSize: 13 }}>{p.email}</span>
          </div>
        </div>
      </Section>

      {/* Delete user */}
      <Section title="Danger Zone">
        {!confirmDelete ? (
          <button
            onClick={() => setConfirmDelete(true)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors"
            style={{
              borderColor: '#FCA5A5',
              color: '#DC2626',
              backgroundColor: 'transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FEF2F2'; }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            Delete user and all data
          </button>
        ) : (
          <div
            className="rounded-lg border p-3"
            style={{ borderColor: '#FCA5A5', backgroundColor: '#FEF2F2' }}
          >
            <p className="text-sm mb-3" style={{ color: '#DC2626' }}>
              This will permanently delete {p.name || p.email}'s profile, sessions, and intake data.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => onDelete(userId)}
                className="flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors"
                style={{
                  backgroundColor: '#DC2626',
                  color: '#FFFFFF',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#B91C1C'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#DC2626'; }}
              >
                Confirm delete
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-secondary)',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = ''; }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3
        className="text-xs font-medium uppercase tracking-wide mb-2"
        style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div
        className="text-xs font-medium mb-0.5"
        style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
      >
        {label}
      </div>
      <div
        className="text-sm"
        style={{ color: 'var(--color-text-primary)', lineHeight: 1.5 }}
      >
        {value}
      </div>
    </div>
  );
}
