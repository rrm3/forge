/**
 * MyTeamView - Activity Log (everyone) + My Team (managers) views.
 *
 * Shows pre-generated, privacy-sanitized weekly activity summaries.
 * Managers see their direct reports' data; everyone sees their own.
 */

import { Fragment, useEffect, useState, useCallback, useMemo } from 'react';
import { Check, X as XIcon, ChevronRight, ChevronDown, ChevronLeft, ClipboardList, Users, AlertCircle, Lightbulb, BookOpen, Filter, Download } from 'lucide-react';
import { getMyActivity, getTeamMembers } from '../api/client';
import { UserAvatar } from './UserAvatar';
import { getProgramWeek } from '../program';
import type { ActivityReport, ActivityWeek, TeamResponse } from '../api/types';

// ── Shared components ───────────────────────────────────────────────────────

function WeekBadge({ completed, label }: { completed: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1">
      {completed ? (
        <Check className="w-3.5 h-3.5" style={{ color: 'var(--color-success, #22c55e)' }} />
      ) : (
        <XIcon className="w-3.5 h-3.5" style={{ color: 'var(--color-text-placeholder)' }} />
      )}
      <span className="text-xs" style={{ color: completed ? 'var(--color-text-secondary)' : 'var(--color-text-placeholder)' }}>
        {label}
      </span>
    </div>
  );
}

function ParticipationGrid({ members, maxWeek, onSelect }: {
  members: ActivityReport[];
  maxWeek: number;
  onSelect: (member: ActivityReport) => void;
}) {
  const weeks = Array.from({ length: maxWeek }, (_, i) => i + 1);
  const hasHierarchy = members.some(m => (m.depth ?? 1) > 1);

  // Track which manager names are collapsed. Default: all collapsed.
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const managers = new Set<string>();
    for (let i = 0; i < members.length; i++) {
      const myDepth = members[i].depth ?? 1;
      if (i + 1 < members.length && (members[i + 1].depth ?? 1) > myDepth) {
        managers.add(members[i].name);
      }
    }
    return managers;
  });

  const toggleCollapse = useCallback((name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  // Figure out which members are "managers" (have someone at a deeper level after them in DFS order)
  const managerNames = new Set<string>();
  if (hasHierarchy) {
    for (let i = 0; i < members.length; i++) {
      const myDepth = members[i].depth ?? 1;
      if (i + 1 < members.length && (members[i + 1].depth ?? 1) > myDepth) {
        managerNames.add(members[i].name);
      }
    }
  }

  // Filter visible rows based on collapse state.
  // DFS order means each person's ancestors are the stack of people above them
  // at decreasing depth levels. If ANY ancestor is collapsed, hide this row.
  const visibleMembers = hasHierarchy ? members.filter((_m, i) => {
    const myDepth = _m.depth ?? 1;
    if (myDepth === 1) return true;
    // Walk backwards to find ancestors and check if any are collapsed
    let lookingForDepth = myDepth - 1;
    for (let j = i - 1; j >= 0 && lookingForDepth >= 1; j--) {
      const d = members[j].depth ?? 1;
      if (d === lookingForDepth) {
        if (collapsed.has(members[j].name)) return false;
        lookingForDepth--;
      }
    }
    return true;
  }) : members;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={{ borderCollapse: 'separate', borderSpacing: 0 }}>
        <thead>
          <tr>
            <th className="text-left py-2 px-3 font-medium sticky left-0 z-10" style={{
              color: 'var(--color-text-secondary)',
              backgroundColor: 'var(--color-surface-white)',
              minWidth: 200,
            }}>
              Team member
            </th>
            {weeks.map(w => (
              <th key={w} colSpan={2} className="text-center py-2 px-1 font-medium" style={{
                color: 'var(--color-text-secondary)',
                borderBottom: '1px solid var(--color-border)',
              }}>
                <span className="text-xs">Day {w}</span>
              </th>
            ))}
          </tr>
          <tr>
            <th className="sticky left-0 z-10" style={{ backgroundColor: 'var(--color-surface-white)' }} />
            {weeks.map(w => (
              <Fragment key={w}>
                <th className="text-center px-1 py-1" style={{ color: 'var(--color-text-placeholder)' }}>
                  <span className="text-[10px]">Plan</span>
                </th>
                <th className="text-center px-1 py-1" style={{ color: 'var(--color-text-placeholder)' }}>
                  <span className="text-[10px]">Wrap</span>
                </th>
              </Fragment>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleMembers.map(m => {
            const depth = m.depth ?? 1;
            const isManager = managerNames.has(m.name);
            const isCollapsed = collapsed.has(m.name);
            const indent = hasHierarchy ? (depth - 1) * 20 : 0;

            return (
              <tr
                key={m.user_id || m.name}
                className="cursor-pointer transition-colors hover:bg-[var(--color-surface-raised)]"
                onClick={() => onSelect(m)}
              >
                <td className="py-2 px-3 sticky left-0 z-10" style={{ backgroundColor: 'var(--color-surface-white)' }}>
                  <div className="flex items-center gap-2" style={{ paddingLeft: indent }}>
                    {hasHierarchy && isManager && (
                      <button
                        onClick={(e) => toggleCollapse(m.name, e)}
                        className="flex-shrink-0 p-0.5 rounded hover:bg-[var(--color-surface-raised)]"
                      >
                        {isCollapsed
                          ? <ChevronRight className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
                          : <ChevronDown className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
                        }
                      </button>
                    )}
                    {hasHierarchy && !isManager && (
                      <span className="w-4" />
                    )}
                    <UserAvatar name={m.name} avatarUrl={m.avatar_url} size={28} />
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>
                        {m.name}
                      </div>
                      <div className="text-xs truncate" style={{ color: 'var(--color-text-muted)' }}>
                        {m.title || m.department || ''}
                      </div>
                    </div>
                  </div>
                </td>
                {weeks.map(w => {
                  const week = m.weeks?.[String(w)];
                  return (
                    <Fragment key={w}>
                      <td className="text-center px-1 py-2">
                        {week?.intake_completed ? (
                          <Check className="w-3.5 h-3.5 mx-auto" style={{ color: 'var(--color-success, #22c55e)' }} />
                        ) : (
                          <span className="block w-3.5 h-3.5 mx-auto rounded-full" style={{ backgroundColor: m.has_profile ? 'var(--color-border)' : 'transparent' }} />
                        )}
                      </td>
                      <td className="text-center px-1 py-2">
                        {week?.wrapup_completed ? (
                          <Check className="w-3.5 h-3.5 mx-auto" style={{ color: 'var(--color-success, #22c55e)' }} />
                        ) : (
                          <span className="block w-3.5 h-3.5 mx-auto rounded-full" style={{ backgroundColor: m.has_profile ? 'var(--color-border)' : 'transparent' }} />
                        )}
                      </td>
                    </Fragment>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


function WeekDetail({ week, weekNum }: { week: ActivityWeek; weekNum: number }) {
  return (
    <div
      className="rounded-lg border p-4"
      style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          Day {weekNum}
        </h4>
        <div className="flex items-center gap-3">
          <WeekBadge completed={week.intake_completed} label={weekNum <= 1 ? 'Getting Started' : 'Plan'} />
          <WeekBadge completed={week.wrapup_completed} label="Wrap-up" />
        </div>
      </div>

      {week.plan && week.plan !== 'No plan recorded' && week.plan !== 'Summary generation failed' && (
        <div className="mb-3">
          <div className="text-xs font-medium mb-1 flex items-center gap-1.5" style={{ color: 'var(--color-text-muted)' }}>
            <ClipboardList className="w-3 h-3" />
            Plan
          </div>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{week.plan}</p>
        </div>
      )}

      {week.accomplished && week.accomplished !== 'No activity recorded' && week.accomplished !== 'Summary generation failed' && (
        <div className="mb-3">
          <div className="text-xs font-medium mb-1 flex items-center gap-1.5" style={{ color: 'var(--color-text-muted)' }}>
            <Check className="w-3 h-3" />
            Accomplished
          </div>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>{week.accomplished}</p>
        </div>
      )}

      {week.insights && week.insights.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-medium mb-1 flex items-center gap-1.5" style={{ color: 'var(--color-text-muted)' }}>
            <AlertCircle className="w-3 h-3" />
            Notable
          </div>
          <ul className="space-y-1">
            {week.insights.map((insight, i) => (
              <li key={i} className="text-sm flex items-start gap-1.5" style={{ color: 'var(--color-text-secondary)' }}>
                <span style={{ color: 'var(--color-text-placeholder)' }}>*</span>
                {insight}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(week.tips_shared > 0 || week.ideas_count > 0 || (week.collabs_started ?? 0) > 0) && (
        <div className="flex items-center gap-4 pt-2 border-t" style={{ borderColor: 'var(--color-border)' }}>
          {week.tips_shared > 0 && (
            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              <BookOpen className="w-3 h-3" />
              {week.tips_shared} tip{week.tips_shared !== 1 ? 's' : ''} shared
            </div>
          )}
          {(week.collabs_started ?? 0) > 0 && (
            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              <Users className="w-3 h-3" />
              {week.collabs_started} collab{week.collabs_started !== 1 ? 's' : ''} proposed
            </div>
          )}
          {week.ideas_count > 0 && (
            <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              <Lightbulb className="w-3 h-3" />
              {week.ideas_count} idea{week.ideas_count !== 1 ? 's' : ''} explored
            </div>
          )}
        </div>
      )}

      {!week.intake_completed && !week.wrapup_completed && (
        <p className="text-sm italic" style={{ color: 'var(--color-text-placeholder)' }}>
          No activity recorded for this day.
        </p>
      )}
    </div>
  );
}

function MemberDetail({ report, onBack }: { report: ActivityReport; onBack?: () => void }) {
  const maxWeek = getProgramWeek();
  const weeks = Array.from({ length: maxWeek }, (_, i) => i + 1).reverse();

  return (
    <div>
      {onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-1 mb-4 text-sm font-medium transition-colors hover:opacity-80"
          style={{ color: 'var(--color-primary)' }}
        >
          <ChevronLeft className="w-4 h-4" />
          Back to team
        </button>
      )}

      <div className="flex items-center gap-3 mb-6">
        <UserAvatar name={report.name} avatarUrl={report.avatar_url} size={40} />
        <div>
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {report.name}
          </h3>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            {[report.title, report.department].filter(Boolean).join(' · ')}
          </p>
        </div>
      </div>

      {!report.has_report ? (
        <div
          className="rounded-lg border p-6 text-center"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
        >
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            {report.has_profile
              ? 'No activity data available yet.'
              : 'This person has not joined AI Tuesdays yet.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {weeks.map(w => {
            const week = report.weeks?.[String(w)];
            if (!week) return null;
            return <WeekDetail key={w} week={week} weekNum={w} />;
          })}
        </div>
      )}
    </div>
  );
}


// ── Activity Log (visible to everyone) ──────────────────────────────────────

export function ActivityLogView() {
  const [report, setReport] = useState<ActivityReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyActivity()
      .then(r => { setReport(r); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 rounded" style={{ backgroundColor: 'var(--color-border)' }} />
          <div className="h-32 rounded" style={{ backgroundColor: 'var(--color-border)' }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm" style={{ color: 'var(--color-error)' }}>Failed to load activity: {error}</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          Activity Log
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
          Your AI Tuesday activity, week by week. This is the same information visible to your manager.
        </p>
      </div>

      {!report?.has_report ? (
        <div
          className="rounded-lg border p-6 text-center"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
        >
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            No activity data available yet. Complete your check-in and wrap-up to see your activity here.
          </p>
        </div>
      ) : (
        <MemberDetail report={report} />
      )}
    </div>
    </div>
  );
}


// ── My Team (visible to managers) ───────────────────────────────────────────

type FilterMode = 'all' | 'missing-intake' | 'missing-wrapup' | 'no-activity' | 'not-joined';

function csvSafe(value: string): string {
  let s = (value || '').replace(/"/g, '""');
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return `"${s}"`;
}

function exportParticipationCsv(members: ActivityReport[], maxWeek: number) {
  const weeks = Array.from({ length: maxWeek }, (_, i) => i + 1);
  const header = ['Name', 'Title', 'Department',
    ...weeks.flatMap(w => [`Day ${w} Plan`, `Day ${w} Wrap-up`]),
  ].join(',');

  const rows = members.map(m => {
    const cells = [
      csvSafe(m.name || ''),
      csvSafe(m.title || ''),
      csvSafe(m.department || ''),
    ];
    for (const w of weeks) {
      const week = m.weeks?.[String(w)];
      cells.push(week?.intake_completed ? 'Yes' : 'No');
      cells.push(week?.wrapup_completed ? 'Yes' : 'No');
    }
    return cells.join(',');
  });

  const csv = [header, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `ai-tuesdays-participation-week${maxWeek}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function MyTeamView() {
  const [teamData, setTeamData] = useState<TeamResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<ActivityReport | null>(null);
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const [filterWeek, setFilterWeek] = useState<number>(0); // 0 = current week
  const maxWeek = getProgramWeek();

  useEffect(() => {
    getTeamMembers()
      .then(d => { setTeamData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  const members = teamData?.members ?? [];
  const effectiveWeek = filterWeek || maxWeek;

  // All hooks must be above early returns
  const filteredMembers = useMemo(() => {
    if (filterMode === 'all') return members;
    const wk = String(effectiveWeek);
    return members.filter(m => {
      const week = m.weeks?.[wk];
      switch (filterMode) {
        case 'missing-intake': return !week?.intake_completed;
        case 'missing-wrapup': return !week?.wrapup_completed;
        case 'no-activity': return !week?.intake_completed && !week?.wrapup_completed;
        case 'not-joined': return !m.has_profile;
        default: return true;
      }
    });
  }, [members, filterMode, effectiveWeek]);

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 rounded" style={{ backgroundColor: 'var(--color-border)' }} />
          <div className="h-64 rounded" style={{ backgroundColor: 'var(--color-border)' }} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm" style={{ color: 'var(--color-error)' }}>Failed to load team data: {error}</p>
      </div>
    );
  }

  if (!teamData) return null;

  // Stats (always based on full member list)
  const activeThisWeek = members.filter(m => m.weeks?.[String(maxWeek)]?.intake_completed).length;
  const wrappedUpThisWeek = members.filter(m => m.weeks?.[String(maxWeek)]?.wrapup_completed).length;
  const noProfile = members.filter(m => !m.has_profile).length;

  if (selectedMember) {
    return (
      <div className="h-full overflow-y-auto">
      <div className="p-6 max-w-3xl mx-auto">
        <MemberDetail
          report={selectedMember}
          onBack={() => setSelectedMember(null)}
        />
      </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          My Team
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>
          AI Tuesday activity for your direct reports. Click a person to see their weekly details.
        </p>
      </div>

      {/* Stats bar */}
      <div
        className="grid grid-cols-4 gap-4 mb-6 p-4 rounded-lg border"
        style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
      >
        <div>
          <div className="text-2xl font-semibold" style={{ color: 'var(--color-text-primary)', fontFamily: "'Geist Mono', monospace" }}>
            {teamData.team_size}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Team members</div>
        </div>
        <div>
          <div className="text-2xl font-semibold" style={{ color: 'var(--color-text-primary)', fontFamily: "'Geist Mono', monospace" }}>
            {activeThisWeek}/{teamData.team_size}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Checked in this week</div>
        </div>
        <div>
          <div className="text-2xl font-semibold" style={{ color: 'var(--color-text-primary)', fontFamily: "'Geist Mono', monospace" }}>
            {wrappedUpThisWeek}/{teamData.team_size}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Wrapped up this week</div>
        </div>
        <div>
          <div className="text-2xl font-semibold" style={{ color: noProfile > 0 ? 'var(--color-warning, #f59e0b)' : 'var(--color-text-primary)', fontFamily: "'Geist Mono', monospace" }}>
            {noProfile}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Not yet joined</div>
        </div>
      </div>

      {/* Filter bar + export */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5" style={{ color: 'var(--color-text-muted)' }} />
          <select
            value={filterMode}
            onChange={e => setFilterMode(e.target.value as FilterMode)}
            className="text-sm rounded-md border px-2 py-1.5 outline-none"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-surface-white)' }}
          >
            <option value="all">All members</option>
            <option value="missing-intake">Missing plan</option>
            <option value="missing-wrapup">Missing wrap-up</option>
            <option value="no-activity">No activity</option>
            <option value="not-joined">Not yet joined</option>
          </select>
          {filterMode !== 'all' && filterMode !== 'not-joined' && (
            <select
              value={filterWeek}
              onChange={e => setFilterWeek(Number(e.target.value))}
              className="text-sm rounded-md border px-2 py-1.5 outline-none"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)', backgroundColor: 'var(--color-surface-white)' }}
            >
              <option value={0}>Current week (Day {maxWeek})</option>
              {Array.from({ length: maxWeek }, (_, i) => i + 1).map(w => (
                <option key={w} value={w}>Day {w}</option>
              ))}
            </select>
          )}
          {filterMode !== 'all' && (
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {filteredMembers.length} of {members.length}
            </span>
          )}
        </div>
        <button
          onClick={() => exportParticipationCsv(filterMode === 'all' ? members : filteredMembers, maxWeek)}
          className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border transition-colors hover:bg-[var(--color-surface-raised)]"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
        >
          <Download className="w-3.5 h-3.5" />
          Export CSV
        </button>
      </div>

      {/* Participation grid */}
      <div
        className="rounded-lg border overflow-hidden"
        style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface-white)' }}
      >
        <ParticipationGrid
          members={filteredMembers}
          maxWeek={maxWeek}
          onSelect={setSelectedMember}
        />
      </div>

      {/* Click hint */}
      {filteredMembers.length > 0 && (
        <div className="flex items-center gap-1.5 mt-3" style={{ color: 'var(--color-text-placeholder)' }}>
          <ChevronRight className="w-3.5 h-3.5" />
          <span className="text-xs">Click a row to see weekly details</span>
        </div>
      )}
      {filteredMembers.length === 0 && filterMode !== 'all' && (
        <div className="text-center py-8">
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            No members match this filter.
          </p>
        </div>
      )}
    </div>
    </div>
  );
}
