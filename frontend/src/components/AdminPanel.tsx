/**
 * AdminPanel - Department objectives and context management.
 * Rendered as a child of AdminLayout (no back link, heading, or mobile gate needed).
 */

import { useEffect, useState, useRef } from 'react';
import { Plus, Trash2, Save, X, ChevronDown, ChevronUp } from 'lucide-react';
import { getAdminAccess, getDepartmentConfig, saveDepartmentConfig } from '../api/client';
import type { DepartmentConfig, DepartmentObjective } from '../api/types';

type Tab = 'objectives' | 'context';

function generateId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2, 10);
}

export function AdminPanel() {
  const [departments, setDepartments] = useState<string[]>([]);
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [config, setConfig] = useState<DepartmentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('objectives');
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  // Editing state for objectives
  const [editLabel, setEditLabel] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editExtractionKey, setEditExtractionKey] = useState('');
  const [extractionKeyLocked, setExtractionKeyLocked] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  // Context tab state
  const [contextPrompt, setContextPrompt] = useState('');
  const [contextDirty, setContextDirty] = useState(false);

  const labelInputRef = useRef<HTMLInputElement>(null);

  // Load admin access on mount
  useEffect(() => {
    getAdminAccess()
      .then(({ departments: depts }) => {
        setDepartments(depts);
        if (depts.length > 0) {
          setSelectedDept(depts[0]);
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
        setConfig(c);
        setContextPrompt(c.prompt);
        setContextDirty(false);
        setExpandedCard(null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedDept]);

  function expandObjective(obj: DepartmentObjective) {
    setExpandedCard(obj.id);
    setEditLabel(obj.label);
    setEditDescription(obj.description);
    setEditExtractionKey(obj.extraction_key);
    setExtractionKeyLocked(!!obj.extraction_key);
    setTimeout(() => labelInputRef.current?.focus(), 50);
  }

  function collapseCard() {
    setExpandedCard(null);
    setEditLabel('');
    setEditDescription('');
    setEditExtractionKey('');
    setExtractionKeyLocked(false);
  }

  async function saveObjective(id: string) {
    if (!config) return;
    setSaving(true);
    const updated: DepartmentConfig = {
      ...config,
      objectives: config.objectives.map((o) =>
        o.id === id
          ? { ...o, label: editLabel, description: editDescription, extraction_key: editExtractionKey }
          : o
      ),
    };
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setConfig(updated);
      collapseCard();
      flashSave('Objective saved');
    } catch {
      flashSave('Failed to save');
    } finally {
      setSaving(false);
    }
  }

  async function deleteObjective(id: string) {
    if (!config || config.objectives.length <= 1) return;
    setSaving(true);
    const updated: DepartmentConfig = {
      ...config,
      objectives: config.objectives.filter((o) => o.id !== id),
    };
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setConfig(updated);
      collapseCard();
      flashSave('Objective deleted');
    } catch {
      flashSave('Failed to delete');
    } finally {
      setSaving(false);
    }
  }

  async function addObjective() {
    if (!config) return;
    const newObj: DepartmentObjective = {
      id: generateId(),
      label: 'New Objective',
      description: '',
      extraction_key: '',
    };
    const updated: DepartmentConfig = {
      ...config,
      objectives: [...config.objectives, newObj],
    };
    setSaving(true);
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setConfig(updated);
      expandObjective(newObj);
      flashSave('Objective added');
    } catch {
      flashSave('Failed to add');
    } finally {
      setSaving(false);
    }
  }

  async function saveContext() {
    if (!config) return;
    setSaving(true);
    const updated: DepartmentConfig = { ...config, prompt: contextPrompt };
    try {
      await saveDepartmentConfig(selectedDept, updated);
      setConfig(updated);
      setContextDirty(false);
      flashSave('Context saved');
    } catch {
      flashSave('Failed to save context');
    } finally {
      setSaving(false);
    }
  }

  function flashSave(msg: string) {
    setSaveMessage(msg);
    setTimeout(() => setSaveMessage(''), 2500);
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

  const tabStyle = (tab: Tab) => ({
    fontSize: 14,
    fontWeight: 500 as const,
    fontFamily: "'Satoshi', system-ui, sans-serif",
    color: activeTab === tab ? 'var(--color-primary)' : 'var(--color-text-muted)',
    borderBottom: activeTab === tab ? '2px solid var(--color-primary)' : '2px solid transparent',
    cursor: 'pointer' as const,
    paddingBottom: 8,
  });

  return (
    <div className="max-w-2xl">
      {/* Department picker */}
      {departments.length > 1 ? (
        <div className="relative inline-block mb-6">
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="appearance-none rounded-md border pl-3 pr-8 py-2 text-sm"
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
        <p
          className="text-sm mb-6"
          style={{
            color: 'var(--color-text-muted)',
            fontFamily: "'Satoshi', system-ui, sans-serif",
          }}
        >
          {selectedDept}
        </p>
      )}

      {/* Tabs */}
      <div className="flex gap-6 mb-6" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <button onClick={() => setActiveTab('objectives')} style={tabStyle('objectives')}>
          Objectives
        </button>
        <button onClick={() => setActiveTab('context')} style={tabStyle('context')}>
          Context
        </button>
      </div>

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

      {/* Objectives tab */}
      {activeTab === 'objectives' && config && (
        <div className="flex flex-col gap-3">
          {config.objectives.map((obj) => {
            const isExpanded = expandedCard === obj.id;
            return (
              <div
                key={obj.id}
                className="rounded-lg border overflow-hidden"
                style={{
                  backgroundColor: '#FFFFFF',
                  borderColor: isExpanded ? 'var(--color-primary)' : 'var(--color-border)',
                }}
              >
                {/* Collapsed header */}
                <button
                  onClick={() => isExpanded ? collapseCard() : expandObjective(obj)}
                  className="flex items-center justify-between w-full px-4 py-3 text-left transition-colors"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={(e) => {
                    if (!isExpanded) e.currentTarget.style.backgroundColor = 'var(--color-surface-raised)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <span
                    className="text-sm"
                    style={{
                      color: 'var(--color-text-primary)',
                      fontFamily: "'Satoshi', system-ui, sans-serif",
                      fontWeight: 450,
                    }}
                  >
                    {obj.label}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 shrink-0 ml-3" style={{ color: 'var(--color-text-placeholder)' }} strokeWidth={1.5} />
                  ) : (
                    <ChevronDown className="w-4 h-4 shrink-0 ml-3" style={{ color: 'var(--color-text-placeholder)' }} strokeWidth={1.5} />
                  )}
                </button>

                {/* Expanded edit form */}
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

                    <div>
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

                    {/* Actions */}
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        onClick={() => saveObjective(obj.id)}
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
                        onClick={collapseCard}
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
                      {config.objectives.length > 1 && (
                        <button
                          onClick={() => deleteObjective(obj.id)}
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
          })}

          {/* Add objective card */}
          <button
            onClick={addObjective}
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
      )}

      {/* Context tab */}
      {activeTab === 'context' && config && (
        <div className="flex flex-col gap-4">
          <div>
            <label
              className="block text-xs font-medium mb-2"
              style={{ color: 'var(--color-text-muted)', fontFamily: "'Satoshi', system-ui, sans-serif" }}
            >
              Department context prompt
            </label>
            <textarea
              value={contextPrompt}
              onChange={(e) => {
                setContextPrompt(e.target.value);
                setContextDirty(true);
              }}
              rows={12}
              placeholder="Provide context about this department that the AI coach should know. Markdown supported."
              className="w-full rounded-md border px-4 py-3 text-sm outline-none resize-y transition-colors"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-primary)',
                fontFamily: "'Satoshi', system-ui, sans-serif",
                lineHeight: 1.6,
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
              onClick={saveContext}
              disabled={saving || !contextDirty}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors"
              style={{
                backgroundColor: saving || !contextDirty ? 'var(--color-border)' : 'var(--color-primary)',
                color: '#FFFFFF',
                cursor: saving || !contextDirty ? 'not-allowed' : 'pointer',
                fontFamily: "'Satoshi', system-ui, sans-serif",
              }}
            >
              <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
              Save context
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
