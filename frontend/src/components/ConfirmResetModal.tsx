import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';
import { intakeTitle } from '../program';

interface ConfirmResetModalProps {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  loading?: boolean;
}

export function ConfirmResetModal({ open, onCancel, onConfirm, loading }: ConfirmResetModalProps) {
  const dayLabel = intakeTitle();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md mx-4 p-6"
        style={{
          backgroundColor: 'var(--color-surface-white, #FFFFFF)',
          borderRadius: '14px',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-4">
          <div
            className="flex items-center justify-center w-10 h-10 rounded-full"
            style={{ backgroundColor: 'rgba(217, 119, 6, 0.1)' }}
          >
            <AlertTriangle className="w-5 h-5" style={{ color: '#D97706' }} />
          </div>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            Reset {dayLabel}?
          </h3>
        </div>

        <div className="space-y-2 mb-6">
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            This will reset your {dayLabel} intake. Your conversation, profile
            data, and ideas captured during this session will be cleared.
          </p>
          <p className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
            You'll need to redo the {dayLabel} intake before continuing.
          </p>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Your other conversations and tips will not be affected.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={loading}
            className="flex-1 px-4 py-2 text-sm font-medium rounded-lg border transition-colors"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-secondary)',
              backgroundColor: 'transparent',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 px-4 py-2 text-sm font-medium rounded-lg transition-colors"
            style={{
              backgroundColor: loading ? '#92400E' : '#D97706',
              color: '#FFFFFF',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Resetting...' : `Reset ${dayLabel}`}
          </button>
        </div>
      </div>
    </div>
  );
}
