/**
 * AdminPanel - Questions management page.
 * Shows company-wide questions (full admins only) and department questions on one page.
 * Rendered as a child of AdminLayout.
 */

import { useEffect, useState, useRef } from 'react';
import { Plus, Trash2, Save, X, ChevronDown, ChevronUp } from 'lucide-react';
import {
  getAdminAccess,
  getDepartmentConfig,
  saveDepartmentConfig,
  getCompanyConfig,
  saveCompanyObjectives,
} from '../api/client';
import type { DepartmentConfig, DepartmentObjective, CompanyConfig } from '../api/types';

function generateId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2, 10);
}

function generateCompanyId(): string {
  return `c0-${crypto.randomUUID?.() ?? Math.random().toString(36).slice(2, 10)}`;
}

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

/** Reusable objective card with expand/collapse editing */
function ObjectiveCard({
  obj,
  isExpanded,
  onExpand,
  onCollapse,
  onSave,
  onDelete,
  canDelete,
  saving,
  labelInputRef,
}: {
  obj: DepartmentObjective;
  isExpanded: boolean;
  onExpand: () => void;
  onCollapse: () => void;
  onSave: (id: string, label: string, description: string, extractionKey: string, weekIntroduced: number) => void;
  onDelete: (id: string) => void;
  canDelete: boolean;
  saving: boolean;
  labelInputRef?: React.RefObject<HTMLInputElement | null>;
}) {
  const [editLabel, setEditLabel] = useState(obj.label);
  const [editDescription, setEditDescription] = useState(obj.description);
  const [editExtractionKey, setEditExtractionKey] = useState(obj.extraction_key);
  const [extractionKeyLocked] = useState(!!obj.extraction_key);
  const [editWeekIntroduced, setEditWeekIntroduced] = useState(obj.week_introduced ?? 1);

  useEffect(() => {
    if (isExpanded) {
      setEditLabel(obj.label);
      setEditDescription(obj.description);
      setEditExtractionKey(obj.extraction_key);
      setEditWeekIntroduced(obj.week_introduced ?? 1);
    }
  }, [isExpanded, obj]);

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{
        backgroundColor: '#FFFFFF',
        borderColor: isExpanded ? 'var(--color-primary)' : 'var(--color-border)',
      }}
    >
      <button
        onClick={() => (isExpanded ? onCollapse() : onExpand())}
        className="flex items-center justify-between w-full px-4 py-3 text-left transition-colors"
        style={{ cursor: 'pointer' }}
        onMouseEnter={(e) => {
          if (!isExpanded) e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span
            className="text-sm truncate"
            style={{
              color: 'var(--color-text-primary)',
              fontFamily: "'Satoshi', system-ui, sans-serif",
              fontWeight: 450,
            }}
          >
            {obj.label}
          </span>
          {(obj.week_introduced ?? 1) > 1 && (
            <span
              className="shrink-0 px-2 py-0.5 rounded-full text-xs font-medium"
              style={{
                backgroundColor: 'var(--color-surface-raised, #F1F5F9)',
                color: 'var(--color-text-muted)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
            >
              Wk {obj.week_introduced}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 shrink-0 ml-3" style={{ color: 'var(--color-text-placeholder)' }} strokeWidth={1.5} />
        ) : (
          <ChevronDown className="w-4 h-4 shrink-0 ml-3" style={{ color: 'var(--color-text-placeholder)' }} strokeWidth={1.5} />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 flex flex-col gap-3" style={{ borderTop: '1px solid var(--color-border)' }}>
          <div className="pt-3">
            <label
              className="block text-xs font-medium mb-1"
              style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
            >
              Label
            </label>
            <input
              ref={labelInputRef}
              type="text"
              value={editLabel}
              onChange={(e) => setEditLabel(e.target.value)}
              className="w-full rounded-md border px-3 py-2 text-sm outline-none transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary)'; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; }}
            />
          </div>

          <div>
            <label
              className="block text-xs font-medium mb-1"
              style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
            >
              Description
            </label>
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              rows={3}
              className="w-full rounded-md border px-3 py-2 text-sm outline-none resize-y transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary)'; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; }}
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label
                className="block text-xs font-medium mb-1"
                style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
              >
                Extraction key
              </label>
              <input
                type="text"
                value={editExtractionKey}
                onChange={(e) => setEditExtractionKey(e.target.value)}
                disabled={extractionKeyLocked}
                placeholder="e.g. ai_tools_used"
                className="w-full rounded-md border px-3 py-2 text-sm outline-none transition-colors"
                style={{
                  borderColor: 'var(--color-border)',
                  color: extractionKeyLocked ? 'var(--color-text-muted)' : 'var(--color-text-primary)',
                  backgroundColor: extractionKeyLocked ? 'var(--color-surface-raised)' : undefined,
                  fontFamily: "'Satoshi', system-ui, sans-serif",
                  cursor: extractionKeyLocked ? 'not-allowed' : undefined,
                }}
                onFocus={(e) => { if (!extractionKeyLocked) e.currentTarget.style.borderColor = 'var(--color-primary)'; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; }}
              />
              <p
                className="text-xs mt-1"
                style={{ color: 'var(--color-text-placeholder)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
              >
                {extractionKeyLocked
                  ? 'This key is locked. Changing it would orphan existing profile data in DynamoDB.'
                  : 'DynamoDB profile field where extracted data is stored (e.g. work_summary, ai_tools_used). This cannot be changed after saving.'}
              </p>
            </div>
            <div style={{ width: 120 }}>
              <label
                className="block text-xs font-medium mb-1"
                style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
              >
                Week introduced
              </label>
              <select
                value={editWeekIntroduced}
                onChange={(e) => setEditWeekIntroduced(Number(e.target.value))}
                className="w-full rounded-md border px-3 py-2 text-sm outline-none transition-colors appearance-none"
                style={{
                  borderColor: 'var(--color-border)',
                  color: 'var(--color-text-primary)',
                  backgroundColor: '#FFFFFF',
                  fontFamily: "'Satoshi', system-ui, sans-serif",
                  cursor: 'pointer',
                }}
              >
                {Array.from({ length: 12 }, (_, i) => i + 1).map((w) => (
                  <option key={w} value={w}>Week {w}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => onSave(obj.id, editLabel, editDescription, editExtractionKey, editWeekIntroduced)}
              disabled={saving || !editLabel.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors"
              style={{
                backgroundColor: saving || !editLabel.trim() ? 'var(--color-border)' : 'var(--color-primary)',
                color: '#FFFFFF',
                cursor: saving || !editLabel.trim() ? 'not-allowed' : 'pointer',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
            >
              <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
              Save
            </button>
            <button
              onClick={onCollapse}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors"
              style={{
                color: 'var(--color-text-muted)',
                cursor: 'pointer',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
            >
              <X className="w-3.5 h-3.5" strokeWidth={1.5} />
              Cancel
            </button>
            {canDelete && (
              <button
                onClick={() => onDelete(obj.id)}
                disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium ml-auto transition-colors"
                style={{
                  color: 'var(--color-error)',
                  cursor: saving ? 'not-allowed' : 'pointer',
                  fontFamily: "'Satoshi', system-ui, sans-serif",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#FEF2F2'; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
              >
                <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function AdminPanel() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [departments, setDepartments] = useState<string[]>([]);
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [deptConfig, setDeptConfig] = useState<DepartmentConfig | null>(null);
  const [companyConfig, setCompanyConfig] = useState<CompanyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  const labelInputRef = useRef<HTMLInputElement>(null);

  // Load admin access on mount
  useEffect(() => {
    getAdminAccess()
      .then(({ is_admin, departments: depts }) => {
        setIsAdmin(is_admin);
        setDepartments(depts);
        if (depts.length > 0) {
          setSelectedDept(depts[0]);
        }
        // Load company config for full admins
        if (is_admin) {
          getCompanyConfig()
            .then((c) => setCompanyConfig(c))
            .catch(() => {});
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Load department config when selection changes
  useEffect(() => {
    if (!selectedDept) return;
    setLoading(true);
    getDepartmentConfig(selectedDept)
      .then((c) => {
        setDeptConfig(c);
        setExpandedCard(null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedDept]);

  function flashSave(msg: string) {
    setSaveMessage(msg);
    setTimeout(() => setSaveMessage(''), 2500);
  }

  // Company objective actions
  async function saveCompanyObjective(id: string, label: string, description: string, extractionKey: string, weekIntroduced: number) {
    if (!companyConfig) return;
    setSaving(true);
    const updated: CompanyConfig = {
      ...companyConfig,
      objectives: companyConfig.objectives.map((o) =>
        o.id === id
          ? { ...o, label, description, extraction_key: extractionKey, week_introduced: weekIntroduced }
          : o
      ),
    };
    try {
      await saveCompanyObjectives(updated.objectives);
      setCompanyConfig(updated);
      setExpandedCard(null);
      flashSave('Objective saved');
    } catch {
      flashSave('Failed to save');
    } finally {
      setSaving(false);
    }
  }

  async function deleteCompanyObjective(id: string) {
    if (!companyConfig) return;
    setSaving(true);
    const updated: CompanyConfig = {
      ...companyConfig,
      objectives: companyConfig.objectives.filter((o) => o.id !== id),
    };
    try {
      await saveCompanyObjectives(updated.objectives);
      setCompanyConfig(updated);
      setExpandedCard(null);
      flashSave('Objective deleted');
    } catch {
      flashSave('Failed to delete');
    } finally {
      setSaving(false);
    }
  }

  async function addCompanyObjective() {
    if (!companyConfig) return;
    const newObj: DepartmentObjective = {
      id: generateCompanyId(),
      label: 'New Objective',
      description: '',
      extraction_key: '',
      week_introduced: 1,
    };
    const updated: CompanyConfig = {
      ...companyConfig,
      objectives: [...companyConfig.objectives, newObj],
    };
    setSaving(true);
    try {
      await saveCompanyObjectives(updated.objectives);
      setCompanyConfig(updated);
      setExpandedCard(newObj.id);
      setTimeout(() => labelInputRef.current?.focus(), 50);
      flashSave('Objective added');
    } catch {
      flashSave('Failed to add');
    } finally {
      setSaving(false);
    }
  }

  // Department objective actions
  async function saveDeptObjective(id: string, label: string, description: string, extractionKey: string, weekIntroduced: number) {
    if (!deptConfig) return;
    setSaving(true);
    const updated: DepartmentConfig = {
      ...deptConfig,
      objectives: deptConfig.objectives.map((o) =>
        o.id === id
          ? { ...o, label, description, extraction_key: extractionKey, week_introduced: weekIntroduced }
          : o
      ),
    };
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setDeptConfig(updated);
      setExpandedCard(null);
      flashSave('Objective saved');
    } catch {
      flashSave('Failed to save');
    } finally {
      setSaving(false);
    }
  }

  async function deleteDeptObjective(id: string) {
    if (!deptConfig || deptConfig.objectives.length <= 1) return;
    setSaving(true);
    const updated: DepartmentConfig = {
      ...deptConfig,
      objectives: deptConfig.objectives.filter((o) => o.id !== id),
    };
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setDeptConfig(updated);
      setExpandedCard(null);
      flashSave('Objective deleted');
    } catch {
      flashSave('Failed to delete');
    } finally {
      setSaving(false);
    }
  }

  async function addDeptObjective() {
    if (!deptConfig) return;
    const newObj: DepartmentObjective = {
      id: generateId(),
      label: 'New Objective',
      description: '',
      extraction_key: '',
      week_introduced: 1,
    };
    const updated: DepartmentConfig = {
      ...deptConfig,
      objectives: [...deptConfig.objectives, newObj],
    };
    setSaving(true);
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setDeptConfig(updated);
      setExpandedCard(newObj.id);
      setTimeout(() => labelInputRef.current?.focus(), 50);
      flashSave('Objective added');
    } catch {
      flashSave('Failed to add');
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

  const companyObjectives = companyConfig?.objectives ?? [];

  return (
    <div className="max-w-2xl">
      {/* Save feedback */}
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

      {/* Company-wide questions - full admins only */}
      {isAdmin && companyConfig && (
        <div className="mb-8">
          <SectionHeader>Company-wide</SectionHeader>
          <p
            className="text-xs mb-3"
            style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
          >
            Intake questions asked of all users across all departments.
          </p>

          <div className="flex flex-col gap-3">
            {companyObjectives.map((obj) => (
              <ObjectiveCard
                key={obj.id}
                obj={obj}
                isExpanded={expandedCard === obj.id}
                onExpand={() => {
                  setExpandedCard(obj.id);
                  setTimeout(() => labelInputRef.current?.focus(), 50);
                }}
                onCollapse={() => setExpandedCard(null)}
                onSave={saveCompanyObjective}
                onDelete={deleteCompanyObjective}
                canDelete={true}
                saving={saving}
                labelInputRef={expandedCard === obj.id ? labelInputRef : undefined}
              />
            ))}

            <button
              onClick={addCompanyObjective}
              disabled={saving}
              className="flex items-center justify-center gap-2 w-full rounded-lg border-2 border-dashed px-4 py-3 text-sm font-medium transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-muted)',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-primary)';
                e.currentTarget.style.color = 'var(--color-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-border)';
                e.currentTarget.style.color = 'var(--color-text-muted)';
              }}
            >
              <Plus className="w-4 h-4" strokeWidth={1.5} />
              Add objective
            </button>
          </div>
        </div>
      )}

      {/* Department questions */}
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

          <div className="flex flex-col gap-3">
            {deptConfig.objectives.map((obj) => (
              <ObjectiveCard
                key={obj.id}
                obj={obj}
                isExpanded={expandedCard === obj.id}
                onExpand={() => {
                  setExpandedCard(obj.id);
                  setTimeout(() => labelInputRef.current?.focus(), 50);
                }}
                onCollapse={() => setExpandedCard(null)}
                onSave={saveDeptObjective}
                onDelete={deleteDeptObjective}
                canDelete={deptConfig.objectives.length > 1}
                saving={saving}
                labelInputRef={expandedCard === obj.id ? labelInputRef : undefined}
              />
            ))}

            <button
              onClick={addDeptObjective}
              disabled={saving}
              className="flex items-center justify-center gap-2 w-full rounded-lg border-2 border-dashed px-4 py-3 text-sm font-medium transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-muted)',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-primary)';
                e.currentTarget.style.color = 'var(--color-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--color-border)';
                e.currentTarget.style.color = 'var(--color-text-muted)';
              }}
            >
              <Plus className="w-4 h-4" strokeWidth={1.5} />
              Add objective
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
