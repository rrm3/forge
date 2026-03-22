/**
 * Debug panel showing intake checklist progress.
 * Only visible when localStorage 'forge-debug' is set to 'true'.
 * Toggle in browser console: localStorage.setItem('forge-debug', 'true')
 */

import { useSession } from '../state/SessionContext';
import { useAdminStore } from '../state/adminStore';

export function IntakeDebugPanel() {
  const { state } = useSession();
  const { intakeChecklist } = state;
  const adminMode = useAdminStore((s) => s.adminMode);

  if (!adminMode) {
    return null;
  }

  if (intakeChecklist.length === 0) {
    return (
      <div style={{
        position: 'fixed',
        top: 56,
        left: 8,
        width: 260,
        padding: '12px 14px',
        backgroundColor: '#1A1F25',
        color: '#94A3B8',
        borderRadius: 10,
        fontSize: 12,
        fontFamily: "'Geist Mono', monospace",
        zIndex: 20,
        opacity: 0.9,
      }}>
        <div style={{ fontWeight: 600, color: '#E2E8F0', marginBottom: 8 }}>
          Intake Progress
        </div>
        <div>Waiting for first exchange...</div>
      </div>
    );
  }

  const done = intakeChecklist.filter((i) => i.done).length;
  const total = intakeChecklist.length;

  return (
    <div style={{
      position: 'fixed',
      top: 56,
      left: 8,
      width: 260,
      padding: '12px 14px',
      backgroundColor: '#1A1F25',
      color: '#94A3B8',
      borderRadius: 10,
      fontSize: 12,
      fontFamily: "'Geist Mono', monospace",
      zIndex: 50,
      opacity: 0.9,
    }}>
      <div style={{
        fontWeight: 600,
        color: '#E2E8F0',
        marginBottom: 8,
        display: 'flex',
        justifyContent: 'space-between',
      }}>
        <span>Intake Progress</span>
        <span style={{ color: done === total ? '#059669' : '#94A3B8' }}>
          {done}/{total}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{
        height: 3,
        backgroundColor: '#334155',
        borderRadius: 2,
        marginBottom: 10,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${(done / total) * 100}%`,
          backgroundColor: done === total ? '#059669' : '#159AC9',
          borderRadius: 2,
          transition: 'width 300ms ease-out',
        }} />
      </div>

      {intakeChecklist.map((item) => (
        <div
          key={item.field}
          title={item.done && item.value ? item.value : undefined}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 6,
            marginBottom: 4,
            color: item.done ? '#059669' : '#64748B',
            cursor: item.done && item.value ? 'help' : undefined,
          }}
        >
          <span style={{ fontSize: 11, marginTop: 1 }}>{item.done ? '\u2713' : '\u25CB'}</span>
          <div>
            <span style={{
              textDecoration: item.done ? 'line-through' : 'none',
              opacity: item.done ? 0.6 : 1,
            }}>
              {item.label}
            </span>
            {item.done && item.value && (
              <div style={{
                fontSize: 10,
                color: '#4ADE80',
                opacity: 0.7,
                marginTop: 1,
                lineHeight: 1.3,
                maxWidth: 220,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {item.value}
              </div>
            )}
          </div>
        </div>
      ))}

      {done === total && (
        <div style={{
          marginTop: 8,
          padding: '4px 8px',
          backgroundColor: '#059669',
          color: 'white',
          borderRadius: 4,
          textAlign: 'center',
          fontWeight: 600,
          fontSize: 11,
        }}>
          COMPLETE
        </div>
      )}
    </div>
  );
}
