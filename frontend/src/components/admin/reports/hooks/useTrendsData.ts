import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../../../../api/client';

export type TrendsMode = 'full' | 'shareable';

export interface TrendsData {
  generated_at: string;
  weeks: { n: number; start: string; end: string; label: string }[];
  engagement: Record<string, unknown[]>;
  cohorts: Record<string, unknown[]>;
  departments: { list: string[]; active_by_week: unknown[]; momentum: unknown[] };
  tools: { canonical: string[]; mentions_by_week: unknown[]; integration_requests_by_week: unknown[] };
  themes: { canonical: string[]; activity_by_week: unknown[] };
  blockers: { canonical: string[]; counts_by_week: unknown[]; persistent: unknown[] };
  sentiment: { levels: string[]; mix_by_week: unknown[]; by_department_by_week: unknown[] };
  ideas: { new_by_week: unknown[]; status_transitions_by_week: unknown[]; top_themes_by_week: unknown[] };
  _named?: Record<string, unknown[]>;
}

export function useTrendsData() {
  const [data, setData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<TrendsMode>('full');

  const fetchTrends = useCallback(async (m: TrendsMode) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams(window.location.search);
      let result: TrendsData;

      if (params.get('fixture') === '1') {
        const resp = await fetch('/trends.sample.json');
        result = await resp.json();
      } else {
        const resp = await apiFetch(`/api/admin/trends?mode=${m}`);
        result = await resp.json();
      }
      setData(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load trends data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTrends(mode);
  }, [mode, fetchTrends]);

  const toggleMode = useCallback(() => {
    setMode((prev) => (prev === 'full' ? 'shareable' : 'full'));
  }, []);

  return { data, loading, error, mode, toggleMode, refetch: () => fetchTrends(mode) };
}
