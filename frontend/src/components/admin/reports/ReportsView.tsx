import { useTrendsData } from './hooks/useTrendsData';
import { TrendChart } from './charts/TrendChart';
import { SparklineRow } from './charts/SparklineRow';
import { StackedBar100 } from './charts/StackedBar100';
import { DivergingStackedBar } from './charts/DivergingStackedBar';
import { SlopeChart } from './charts/SlopeChart';
import { GroupedBar } from './charts/GroupedBar';
import { palette, typography } from './chartTheme';
import { Download, Eye, EyeOff } from 'lucide-react';

export function ReportsView() {
  const { data, loading, error, mode, toggleMode } = useTrendsData();

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#64748B', fontFamily: typography.font }}>
        Loading trends data...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{
        backgroundColor: palette.cardBg,
        border: `1px solid ${palette.cardBorder}`,
        borderRadius: 14,
        padding: 48,
        textAlign: 'center',
      }}>
        <p style={{ color: '#64748B', fontFamily: typography.font, fontSize: 14 }}>
          {error || 'No trends report uploaded yet.'}
        </p>
        <p style={{ color: '#94A3B8', fontFamily: typography.font, fontSize: 13, marginTop: 8 }}>
          Run <code style={{ fontFamily: typography.mono }}>/forge-trends</code> to generate the first report.
        </p>
      </div>
    );
  }

  const weeks = data.weeks;
  const weekLabels = weeks.map((w) => w.label);
  const engagement = data.engagement as any;
  const sentiment = data.sentiment as any;
  const tools = data.tools as any;
  const departments = data.departments as any;
  const ideas = data.ideas as any;
  const blockers = data.blockers as any;
  const named = data._named as any;

  const handlePrint = () => {
    if (mode !== 'shareable') {
      if (confirm('Switch to shareable mode (no names) before downloading?')) {
        toggleMode();
        setTimeout(() => window.print(), 500);
      }
    } else {
      window.print();
    }
  };

  return (
    <div className="reports-dashboard" style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h2 style={{ fontSize: 24, fontWeight: 600, fontFamily: typography.font, color: '#1A1F25', margin: 0 }}>
              AI Tuesdays — Programme Trends
            </h2>
            <p style={{ fontSize: 14, fontFamily: typography.font, color: '#64748B', margin: '4px 0 0' }}>
              Data through {weeks[weeks.length - 1]?.end} ({weeks.length} weeks)
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }} className="no-print">
            <button
              onClick={toggleMode}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 14px', borderRadius: 10,
                border: `1px solid ${palette.cardBorder}`,
                backgroundColor: mode === 'shareable' ? '#059669' : '#FFFFFF',
                color: mode === 'shareable' ? '#FFFFFF' : '#4A5568',
                fontFamily: typography.font, fontSize: 13, fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              {mode === 'shareable' ? <EyeOff size={14} /> : <Eye size={14} />}
              {mode === 'shareable' ? 'Shareable' : 'Full names'}
            </button>
            <button
              onClick={handlePrint}
              disabled={mode !== 'shareable'}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 14px', borderRadius: 10,
                border: `1px solid ${palette.cardBorder}`,
                backgroundColor: '#FFFFFF',
                color: mode === 'shareable' ? '#4A5568' : '#94A3B8',
                fontFamily: typography.font, fontSize: 13, fontWeight: 500,
                cursor: mode === 'shareable' ? 'pointer' : 'not-allowed',
                opacity: mode === 'shareable' ? 1 : 0.5,
              }}
              title={mode !== 'shareable' ? 'Switch to shareable mode to enable PDF export' : 'Download PDF'}
            >
              <Download size={14} />
              PDF
            </button>
          </div>
        </div>
      </div>

      {/* Engagement */}
      <section style={{ marginBottom: 32 }}>
        <TrendChart
          title="Active Users"
          subtitle="Unique users active each week. Bars show absolute count; line shows % of signed-up population."
          labels={weekLabels}
          barData={engagement.active_users.map((u: any) => u.value)}
          barLabel="Active users"
          lineData={engagement.active_users.map((u: any) => u.pct_of_signups)}
          lineLabel="% of signups"
          leftAxisLabel="Users"
          rightAxisLabel="% of signups"
          summaryTiles={weeks.map((w: any, i: number) => ({
            label: w.label,
            value: engagement.active_users[i]?.value ?? '—',
            sub: `${engagement.active_users[i]?.pct_of_signups ?? 0}% of signups`,
          }))}
        />
      </section>

      <section style={{ marginBottom: 32 }}>
        <TrendChart
          title="Retention"
          subtitle="Returning users each week. Line shows retention rate (% of prior week's users who came back)."
          labels={weekLabels}
          barData={engagement.returning_users.map((u: any) => u.value)}
          barLabel="Returning users"
          lineData={engagement.returning_users.map((u: any) => u.retention_rate)}
          lineLabel="Retention %"
          leftAxisLabel="Users"
          rightAxisLabel="Retention %"
          summaryTiles={weeks.map((w: any, i: number) => ({
            label: w.label,
            value: engagement.returning_users[i]?.value ?? '—',
            sub: i === 0 ? 'Baseline' : `${engagement.returning_users[i]?.retention_rate ?? 0}% retained`,
          }))}
        />
      </section>

      {/* Sparklines */}
      <section style={{ marginBottom: 32 }}>
        <SparklineRow
          weekLabels={weekLabels}
          sparklines={[
            {
              label: 'Sessions / User',
              data: engagement.sessions_per_user_avg.map((s: any) => s.value),
              current: engagement.sessions_per_user_avg[engagement.sessions_per_user_avg.length - 1]?.value?.toFixed(1) ?? '—',
            },
            {
              label: 'Messages / Session',
              data: engagement.messages_per_session_avg.map((s: any) => s.value),
              current: engagement.messages_per_session_avg[engagement.messages_per_session_avg.length - 1]?.value?.toFixed(0) ?? '—',
            },
            {
              label: 'Total Sessions',
              data: engagement.sessions_total.map((s: any) => s.value),
              current: engagement.sessions_total[engagement.sessions_total.length - 1]?.value?.toLocaleString() ?? '—',
            },
          ]}
        />
      </section>

      {/* Session Type Mix */}
      <section style={{ marginBottom: 32 }}>
        <StackedBar100
          title="Session Type Mix"
          subtitle="Distribution of session types each week, normalised to 100%."
          labels={weekLabels}
          series={
            (() => {
              const types = ['wrapup', 'chat', 'brainstorm', 'intake', 'tip', 'collab', 'stuck'];
              const colors = ['#159AC9', '#D97706', '#059669', '#94A3B8', '#8B5CF6', '#EC4899', '#DC2626'];
              return types.map((t, i) => ({
                label: t.charAt(0).toUpperCase() + t.slice(1),
                data: engagement.session_type_mix.map((m: any) => m[t] || 0),
                color: colors[i % colors.length],
              }));
            })()
          }
        />
      </section>

      {/* Departments */}
      <section style={{ marginBottom: 32 }}>
        <SlopeChart
          title="Department Participation"
          subtitle="Active users per department over time. Top 8 departments shown."
          labels={weekLabels}
          departments={
            departments.active_by_week.map((d: any) => ({
              name: d.department,
              data: d.weekly.map((w: any) => w.active),
            }))
          }
        />
      </section>

      {/* Department Momentum */}
      <section style={{ marginBottom: 32 }}>
        <div style={{
          backgroundColor: palette.cardBg,
          border: `1px solid ${palette.cardBorder}`,
          borderRadius: 14,
          padding: 24,
        }}>
          <h3 style={{ fontSize: 20, fontWeight: 600, fontFamily: typography.font, color: '#1A1F25', margin: '0 0 4px' }}>
            Department Momentum
          </h3>
          <p style={{ fontSize: 14, fontFamily: typography.font, color: '#64748B', margin: '0 0 16px' }}>
            How many people participated in each department, comparing {weeks.length >= 2 ? `${weeks[weeks.length - 2]?.label} to ${weeks[weeks.length - 1]?.label}` : 'the last two weeks'}.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
            {departments.momentum
              .filter((m: any) => {
                const dept = departments.active_by_week.find((d: any) => d.department === m.department);
                const lastWeek = dept?.weekly?.[dept.weekly.length - 1]?.active ?? 0;
                return lastWeek > 0 || m.delta_last_2_weeks !== 0;
              })
              .sort((a: any, b: any) => Math.abs(b.delta_last_2_weeks) - Math.abs(a.delta_last_2_weeks))
              .map((m: any) => {
                const dept = departments.active_by_week.find((d: any) => d.department === m.department);
                const prevWeek = dept?.weekly?.[dept.weekly.length - 2]?.active ?? 0;
                const thisWeek = dept?.weekly?.[dept.weekly.length - 1]?.active ?? 0;
                const delta = m.delta_last_2_weeks;
                const trendColor = delta > 2 ? '#059669' : delta < -2 ? '#DC2626' : '#64748B';
                const arrow = delta > 0 ? '\u25B2' : delta < 0 ? '\u25BC' : '';
                return (
                  <div
                    key={m.department}
                    style={{
                      padding: '12px 16px', borderRadius: 10,
                      border: `1px solid ${palette.cardBorder}`,
                      backgroundColor: '#FFFFFF',
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 500, fontFamily: typography.font, color: '#1A1F25' }}>
                        {m.department}
                      </div>
                      <div style={{ fontSize: 13, fontFamily: typography.mono, color: '#94A3B8', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
                        {prevWeek} {'\u2192'} {thisWeek} active users
                      </div>
                    </div>
                    <div style={{
                      fontSize: 16, fontWeight: 600, fontFamily: typography.mono,
                      color: trendColor,
                      fontVariantNumeric: 'tabular-nums',
                      display: 'flex', alignItems: 'center', gap: 3,
                      minWidth: 50, justifyContent: 'flex-end',
                    }}>
                      {arrow && <span style={{ fontSize: 10 }}>{arrow}</span>}
                      {Math.abs(delta)}
                    </div>
                  </div>
                );
              })
            }
          </div>
        </div>
      </section>

      {/* Tools */}
      <section style={{ marginBottom: 32 }}>
        <SlopeChart
          title="Tool Mentions"
          subtitle="Mentions of each tool across weeks. Each line shows one tool's independent count."
          labels={weekLabels}
          departments={
            tools.mentions_by_week
              .filter((t: any) => t.tool !== 'Other')
              .slice(0, 10)
              .map((t: any) => ({
                name: t.tool,
                data: t.weekly,
              }))
          }
        />
      </section>

      {weeks.some((w: any) => !w.has_map_data) && (
          <div style={{
            fontSize: 12, fontFamily: typography.font, color: '#94A3B8',
            fontStyle: 'italic', marginTop: -24, marginBottom: 8, paddingLeft: 4,
          }}>
            * {weeks.filter((w: any) => !w.has_map_data).map((w: any) => w.label).join(', ')}: partial tool data (recovered from report summary, not full batch analysis)
          </div>
        )}

      {/* Tool Movers */}
      <section style={{ marginBottom: 32 }}>
        <div style={{
          backgroundColor: palette.cardBg,
          border: `1px solid ${palette.cardBorder}`,
          borderRadius: 14,
          padding: 24,
        }}>
          <h3 style={{ fontSize: 20, fontWeight: 600, fontFamily: typography.font, color: '#1A1F25', margin: '0 0 4px' }}>
            Tool Movers
          </h3>
          <p style={{ fontSize: 14, fontFamily: typography.font, color: '#64748B', margin: '0 0 16px' }}>
            Biggest changes in how often each tool was mentioned in session transcripts, comparing {weeks.length >= 2 ? `${weeks[weeks.length - 2]?.label} to ${weeks[weeks.length - 1]?.label}` : 'the last two weeks'}.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
            {['risers', 'fallers'].map((type) => {
              const toolsWithDelta = tools.mentions_by_week
                .filter((t: any) => t.weekly.length >= 2)
                .map((t: any) => ({
                  tool: t.tool,
                  prev: t.weekly[t.weekly.length - 2],
                  current: t.weekly[t.weekly.length - 1],
                  delta: t.weekly[t.weekly.length - 1] - t.weekly[t.weekly.length - 2],
                }))
                .filter((t: any) => type === 'risers' ? t.delta > 0 : t.delta < 0)
                .sort((a: any, b: any) => type === 'risers' ? b.delta - a.delta : a.delta - b.delta)
                .slice(0, 5);

              return (
                <div key={type}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, fontFamily: typography.font,
                    color: type === 'risers' ? '#059669' : '#DC2626',
                    marginBottom: 8,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}>
                    {type === 'risers' ? 'Rising' : 'Falling'}
                  </div>
                  {toolsWithDelta.map((t: any) => (
                    <div key={t.tool} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '8px 0', borderBottom: `1px solid ${palette.cardBorder}`,
                    }}>
                      <div>
                        <div style={{ fontSize: 13, fontFamily: typography.font, color: '#1A1F25' }}>{t.tool}</div>
                        <div style={{ fontSize: 11, fontFamily: typography.mono, color: '#94A3B8', fontVariantNumeric: 'tabular-nums', marginTop: 1 }}>
                          {t.prev.toLocaleString()} {'\u2192'} {t.current.toLocaleString()} mentions
                        </div>
                      </div>
                      <span style={{
                        fontSize: 14, fontFamily: typography.mono, fontVariantNumeric: 'tabular-nums',
                        color: type === 'risers' ? '#059669' : '#DC2626',
                        display: 'flex', alignItems: 'center', gap: 3,
                      }}>
                        <span style={{ fontSize: 10 }}>{type === 'risers' ? '\u25B2' : '\u25BC'}</span> {Math.abs(t.delta).toLocaleString()}
                      </span>
                    </div>
                  ))}
                  {toolsWithDelta.length === 0 && (
                    <div style={{ fontSize: 13, fontFamily: typography.font, color: '#94A3B8' }}>
                      No significant changes
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Blockers */}
      {blockers.counts_by_week.length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <GroupedBar
            title="Blockers"
            subtitle="Blocker frequency by category across weeks."
            categories={blockers.counts_by_week.map((b: any) => b.blocker)}
            weekLabels={weekLabels}
            series={blockers.counts_by_week.map((b: any) => ({
              category: b.blocker,
              weekly: b.weekly,
            }))}
          />
        </section>
      )}

      {/* Sentiment */}
      <section style={{ marginBottom: 32 }}>
        <DivergingStackedBar
          title="Sentiment"
          subtitle="How participants feel about AI Tuesdays. Positive/excited above zero line, mixed/frustrated below."
          labels={weekLabels}
          sentimentData={sentiment.mix_by_week}
        />
        {sentiment.mix_by_week.some((s: any) => !s.has_data) && (
          <div style={{
            fontSize: 12, fontFamily: typography.font, color: '#94A3B8',
            fontStyle: 'italic', marginTop: 8, paddingLeft: 4,
          }}>
            * {sentiment.mix_by_week.filter((s: any) => !s.has_data).map((s: any) => `Week ${s.week}`).join(', ')}: sentiment data unavailable (wrapup analysis not preserved for this week)
          </div>
        )}
      </section>

      {/* Ideas */}
      <section style={{ marginBottom: 32 }}>
        <TrendChart
          title="New Ideas"
          subtitle="Ideas submitted per week."
          labels={weekLabels}
          barData={ideas.new_by_week.map((i: any) => i.value)}
          barLabel="New ideas"
          leftAxisLabel="Ideas"
          summaryTiles={weeks.map((w: any, i: number) => ({
            label: w.label,
            value: ideas.new_by_week[i]?.value ?? '—',
          }))}
        />
      </section>

      {/* Named sections (MB only) */}
      {mode === 'full' && named && (
        <>
          {named.top_active_users_by_week?.length > 0 && (
            <section style={{ marginBottom: 32 }}>
              <div style={{
                backgroundColor: palette.cardBg,
                border: `1px solid ${palette.cardBorder}`,
                borderRadius: 14,
                padding: 24,
              }}>
                <h3 style={{ fontSize: 20, fontWeight: 600, fontFamily: typography.font, color: '#1A1F25', margin: '0 0 16px' }}>
                  Top Active Users
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(weeks.length, 4)}, 1fr)`, gap: 16 }}>
                  {named.top_active_users_by_week.map((wk: any) => (
                    <div key={wk.week}>
                      <div style={{
                        fontSize: 12, fontWeight: 600, fontFamily: typography.font,
                        color: '#64748B', marginBottom: 8, textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}>
                        Week {wk.week}
                      </div>
                      {wk.users.slice(0, 5).map((u: any, i: number) => (
                        <div key={u.user_id || i} style={{
                          fontSize: 13, fontFamily: typography.font, color: '#1A1F25',
                          padding: '4px 0', display: 'flex', justifyContent: 'space-between',
                        }}>
                          <span>{u.name || u.user_id.slice(0, 8)}</span>
                          <span style={{
                            fontFamily: typography.mono, fontVariantNumeric: 'tabular-nums',
                            color: '#64748B', fontSize: 12,
                          }}>
                            {u.sessions} sessions
                          </span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {named.attributed_quotes?.length > 0 && (
            <section style={{ marginBottom: 32 }}>
              <div style={{
                backgroundColor: palette.cardBg,
                border: `1px solid ${palette.cardBorder}`,
                borderRadius: 14,
                padding: 24,
              }}>
                <h3 style={{ fontSize: 20, fontWeight: 600, fontFamily: typography.font, color: '#1A1F25', margin: '0 0 16px' }}>
                  Notable Quotes
                </h3>
                {named.attributed_quotes.slice(0, 10).map((q: any, i: number) => (
                  <blockquote key={i} style={{
                    borderLeft: `3px solid ${palette.sentiment[q.sentiment] || palette.barPrimary}`,
                    paddingLeft: 16, margin: '12px 0',
                  }}>
                    <p style={{ fontSize: 14, fontFamily: typography.font, color: '#1A1F25', fontStyle: 'italic', margin: 0 }}>
                      "{q.quote}"
                    </p>
                    <footer style={{ fontSize: 12, fontFamily: typography.font, color: '#64748B', marginTop: 4 }}>
                      {q.name} ({q.department}) — Week {q.week}
                    </footer>
                  </blockquote>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {/* Print styles */}
      <style>{`
        @media print {
          .no-print { display: none !important; }
          .reports-dashboard { max-width: 100% !important; }
          @page { size: landscape; margin: 1cm; }
          section { break-inside: avoid; }
        }
      `}</style>
    </div>
  );
}
