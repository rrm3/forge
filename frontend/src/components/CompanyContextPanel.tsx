/**
 * CompanyContextPanel - System Prompts management page.
 * Shows company-wide prompt (full admins only) and department prompt on one page.
 * Rendered as a child of AdminLayout. Full admin only.
 */

import { useEffect, useState } from 'react';
import { Save, ChevronDown } from 'lucide-react';
import {
  getAdminAccess,
  getDepartmentConfig,
  saveDepartmentConfig,
  getCompanyConfig,
  saveCompanyPrompt,
} from '../api/client';
import type { DepartmentConfig, CompanyConfig } from '../api/types';

/** Reusable section header styled as small-caps muted label */
function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="text-xs font-medium tracking-wider uppercase mb-4"
      style={{
        color: 'var(--color-text-muted)',
        fontFamily: "'Satoshi', system-ui, sans-serif",
        letterSpacing: '0.08em',
      }}
    >
      {children}
    </h2>
  );
}

export function CompanyContextPanel() {
  const [departments, setDepartments] = useState<string[]>([]);
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [deptConfig, setDeptConfig] = useState<DepartmentConfig | null>(null);
  const [companyConfig, setCompanyConfig] = useState<CompanyConfig | null>(null);
  const [loading, setLoading] = useState(true);

  // Company prompt state
  const [companyPrompt, setCompanyPrompt] = useState('');
  const [companyDirty, setCompanyDirty] = useState(false);
  const [companySaving, setCompanySaving] = useState(false);
  const [companySaveMessage, setCompanySaveMessage] = useState('');

  // Department prompt state
  const [deptPrompt, setDeptPrompt] = useState('');
  const [deptDirty, setDeptDirty] = useState(false);
  const [deptSaving, setDeptSaving] = useState(false);
  const [deptSaveMessage, setDeptSaveMessage] = useState('');

  // Load admin access and company config on mount
  useEffect(() => {
    getAdminAccess()
      .then(({ departments: depts }) => {
        setDepartments(depts);
        if (depts.length > 0) {
          setSelectedDept(depts[0]);
        }

        getCompanyConfig()
          .then((c) => {
            setCompanyConfig(c);
            setCompanyPrompt(c.prompt || '');
            setLoading(false);
          })
          .catch(() => setLoading(false));
      })
      .catch(() => setLoading(false));
  }, []);

  // Load department config when selection changes
  useEffect(() => {
    if (!selectedDept) return;
    getDepartmentConfig(selectedDept)
      .then((c) => {
        setDeptConfig(c);
        setDeptPrompt(c.prompt);
        setDeptDirty(false);
      })
      .catch(() => {});
  }, [selectedDept]);

  async function saveCompanyContext() {
    if (!companyConfig) return;
    setCompanySaving(true);
    try {
      await saveCompanyPrompt(companyPrompt);
      setCompanyConfig({ ...companyConfig, prompt: companyPrompt });
      setCompanyDirty(false);
      flashCompanySave('Prompt saved');
    } catch {
      flashCompanySave('Failed to save');
    } finally {
      setCompanySaving(false);
    }
  }

  async function saveDeptContext() {
    if (!deptConfig) return;
    setDeptSaving(true);
    const updated: DepartmentConfig = { ...deptConfig, prompt: deptPrompt };
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setDeptConfig(updated);
      setDeptDirty(false);
      flashDeptSave('Prompt saved');
    } catch {
      flashDeptSave('Failed to save');
    } finally {
      setDeptSaving(false);
    }
  }

  function flashCompanySave(msg: string) {
    setCompanySaveMessage(msg);
    setTimeout(() => setCompanySaveMessage(''), 2500);
  }

  function flashDeptSave(msg: string) {
    setDeptSaveMessage(msg);
    setTimeout(() => setDeptSaveMessage(''), 2500);
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
      {/* Warning banner */}
      <div
        className="px-3 py-2 rounded-md text-xs mb-6"
        style={{
          backgroundColor: '#FFFBEB',
          color: '#92400E',
          fontFamily: "'Satoshi', system-ui, sans-serif",
          lineHeight: 1.5,
        }}
      >
        Be careful editing these prompts. Changes affect the AI system prompt for all users. Only edit if you know what you're doing.
      </div>

      {/* Company-wide prompt */}
      {companyConfig && (
        <div className="mb-8">
          <SectionHeader>Company-wide</SectionHeader>

          {companySaveMessage && (
            <div
              className="mb-4 px-3 py-2 rounded-md text-sm font-medium"
              style={{
                backgroundColor: companySaveMessage.includes('Failed') ? '#FEF2F2' : '#F0FDF4',
                color: companySaveMessage.includes('Failed') ? 'var(--color-error)' : 'var(--color-success)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
            >
              {companySaveMessage}
            </div>
          )}

          <div className="flex flex-col gap-4">
            <div>
              <label
                className="block text-xs font-medium mb-2"
                style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
              >
                Company context prompt
              </label>
              <textarea
                value={companyPrompt}
                onChange={(e) => {
                  setCompanyPrompt(e.target.value);
                  setCompanyDirty(true);
                }}
                rows={12}
                placeholder="Provide company-wide context that the AI coach should know across all departments and sessions."
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
                onClick={saveCompanyContext}
                disabled={companySaving || !companyDirty}
                className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors"
                style={{
                  backgroundColor: companySaving || !companyDirty ? 'var(--color-border)' : 'var(--color-primary)',
                  color: '#FFFFFF',
                  cursor: companySaving || !companyDirty ? 'not-allowed' : 'pointer',
                  fontFamily: "'Satoshi', system-ui, sans-serif",
                }}
              >
                <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
                Save prompt
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Department prompt */}
      {deptConfig && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <h2
              className="text-xs font-medium tracking-wider uppercase"
              style={{
                color: 'var(--color-text-muted)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
                letterSpacing: '0.08em',
              }}
            >
              Department:
            </h2>
            {departments.length > 1 ? (
              <div className="relative inline-block">
                <select
                  value={selectedDept}
                  onChange={(e) => setSelectedDept(e.target.value)}
                  className="appearance-none rounded-md border pl-3 pr-8 py-1.5 text-sm"
                  style={{
                    borderColor: 'var(--color-border)',
                    backgroundColor: '#FFFFFF',
                    color: 'var(--color-text-primary)',
                    fontFamily: "'Satoshi', system-ui, sans-serif",
                    cursor: 'pointer',
                  }}
                >
                  {departments.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
                <ChevronDown
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ width: 14, height: 14, color: 'var(--color-text-muted)' }}
                  strokeWidth={1.5}
                />
              </div>
            ) : (
              <span
                className="text-xs font-medium tracking-wider uppercase"
                style={{
                  color: 'var(--color-text-muted)',
                  fontFamily: "'Satoshi', system-ui, sans-serif",
                  letterSpacing: '0.08em',
                }}
              >
                {selectedDept}
              </span>
            )}
          </div>

          {deptSaveMessage && (
            <div
              className="mb-4 px-3 py-2 rounded-md text-sm font-medium"
              style={{
                backgroundColor: deptSaveMessage.includes('Failed') ? '#FEF2F2' : '#F0FDF4',
                color: deptSaveMessage.includes('Failed') ? 'var(--color-error)' : 'var(--color-success)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
            >
              {deptSaveMessage}
            </div>
          )}

          <div className="flex flex-col gap-4">
            <div>
              <label
                className="block text-xs font-medium mb-2"
                style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
              >
                Department context prompt
              </label>
              <textarea
                value={deptPrompt}
                onChange={(e) => {
                  setDeptPrompt(e.target.value);
                  setDeptDirty(true);
                }}
                rows={12}
                placeholder="Provide context about this department that the AI coach should know. Markdown supported."
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
                This text is included in the AI system prompt for all users in this department.
              </p>
            </div>

            <div>
              <button
                onClick={saveDeptContext}
                disabled={deptSaving || !deptDirty}
                className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors"
                style={{
                  backgroundColor: deptSaving || !deptDirty ? 'var(--color-border)' : 'var(--color-primary)',
                  color: '#FFFFFF',
                  cursor: deptSaving || !deptDirty ? 'not-allowed' : 'pointer',
                  fontFamily: "'Satoshi', system-ui, sans-serif",
                }}
              >
                <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
                Save prompt
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
