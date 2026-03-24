/**
 * CompanyContextPanel - Company-wide context prompt management.
 * Rendered as a child of AdminLayout. Full admin only.
 */

import { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import { getCompanyConfig, saveCompanyConfig } from '../api/client';

export function CompanyContextPanel() {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    getCompanyConfig()
      .then((c) => {
        setPrompt(c.prompt || '');
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    try {
      await saveCompanyConfig({ prompt });
      setDirty(false);
      setSaveMessage('Saved');
      setTimeout(() => setSaveMessage(''), 2500);
    } catch {
      setSaveMessage('Failed to save');
      setTimeout(() => setSaveMessage(''), 2500);
    } finally {
      setSaving(false);
    }
  }

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

  return (
    <div className="max-w-2xl">
      {saveMessage && (
        <div
          className="mb-4 px-3 py-2 rounded-md text-sm font-medium"
          style={{
            backgroundColor: saveMessage.includes('Failed') ? '#FEF2F2' : '#F0FDF4',
            color: saveMessage.includes('Failed') ? 'var(--color-error)' : 'var(--color-success)',
            fontFamily: "'Satoshi', system-ui, sans-serif",
          }}
        >
          {saveMessage}
        </div>
      )}

      <div
        className="mb-4 px-3 py-2 rounded-md text-xs"
        style={{
          backgroundColor: '#FFFBEB',
          color: '#92400E',
          fontFamily: "'Satoshi', system-ui, sans-serif",
          lineHeight: 1.5,
        }}
      >
        Be careful editing this - changes affect the AI system prompt for all users across all sessions company-wide. Only edit if you know what you're doing.
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label
            className="block text-xs font-medium mb-2"
            style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
          >
            Company context prompt
          </label>
          <textarea
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              setDirty(true);
            }}
            rows={16}
            placeholder="Provide company-wide context that the AI coach should know across all departments and sessions. For example: approved AI tools, company policies, program goals."
            className="w-full rounded-md border px-4 py-3 text-sm outline-none resize-y transition-colors"
            style={{
              borderColor: 'var(--color-border)',
              color: 'var(--color-text-primary)',
              fontFamily: "'SF Mono', 'Fira Code', 'Cascadia Code', monospace",
              lineHeight: 1.6,
              fontSize: 13,
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary)'; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; }}
          />
          <p
            className="text-xs mt-1"
            style={{ color: 'var(--color-text-placeholder)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
          >
            This text is included in the AI system prompt for all users across all sessions.
          </p>
        </div>

        <div>
          <button
            onClick={save}
            disabled={saving || !dirty}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={{
              backgroundColor: saving || !dirty ? 'var(--color-border)' : 'var(--color-primary)',
              color: '#FFFFFF',
              cursor: saving || !dirty ? 'not-allowed' : 'pointer',
              fontFamily: "'Satoshi', system-ui, sans-serif",
            }}
          >
            <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
            Save context
          </button>
        </div>
      </div>
    </div>
  );
}
