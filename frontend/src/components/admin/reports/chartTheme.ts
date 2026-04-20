import type { ChartOptions, ScaleOptions } from 'chart.js';

export const palette = {
  barPrimary: '#159AC9',
  barFade: (i: number, total: number) =>
    `rgba(21,154,201,${(0.6 + (i / Math.max(total - 1, 1)) * 0.4).toFixed(2)})`,
  lineAccent: '#D97706',
  gridline: '#E2E8F0',
  axisText: '#64748B',
  axisTitleText: '#4A5568',
  cardBg: '#FAFBFC',
  cardBorder: '#E2E8F0',
  sentiment: {
    frustrated: '#DC2626',
    mixed: '#D97706',
    neutral: '#94A3B8',
    positive: '#159AC9',
    excited: '#1287B3',
  } as Record<string, string>,
  heatmapRamp: ['#E8F4F8', '#B8DDE9', '#7EC0D7', '#4AA3C5', '#1287B3'],
  departmentColors: [
    '#159AC9', '#D97706', '#059669', '#DC2626', '#8B5CF6',
    '#EC4899', '#F59E0B', '#6366F1', '#14B8A6', '#EF4444',
    '#10B981', '#3B82F6', '#A855F7', '#F97316', '#06B6D4',
  ],
};

export const typography = {
  font: "'Satoshi', system-ui, sans-serif",
  mono: "'Geist Mono', ui-monospace, monospace",
};

const baseScale: Partial<ScaleOptions<'linear'>> = {
  grid: { color: palette.gridline },
  ticks: {
    color: palette.axisText,
    font: { family: typography.mono, size: 12 },
  },
  title: {
    color: palette.axisTitleText,
    font: { family: typography.font, size: 12, weight: 500 },
  },
};

export function barLineOptions(opts: {
  leftLabel?: string;
  rightLabel?: string;
  stacked?: boolean;
}): ChartOptions<'bar'> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300, easing: 'easeOutQuart' },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'start',
        labels: {
          font: { family: typography.font, size: 12 },
          color: palette.axisText,
          usePointStyle: true,
          pointStyle: 'rectRounded',
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: '#1A1F25',
        titleFont: { family: typography.font, size: 13 },
        bodyFont: { family: typography.mono, size: 12 },
        cornerRadius: 8,
        padding: 10,
        displayColors: true,
      },
    },
    scales: {
      x: {
        ...baseScale,
        grid: { display: false },
      },
      y: {
        ...baseScale,
        position: 'left',
        title: { display: !!opts.leftLabel, text: opts.leftLabel },
        stacked: opts.stacked,
      },
      ...(opts.rightLabel
        ? {
            y1: {
              ...baseScale,
              position: 'right' as const,
              title: { display: true, text: opts.rightLabel },
              grid: { drawOnChartArea: false },
              ticks: {
                ...baseScale.ticks,
                color: palette.lineAccent,
                callback: (v: unknown) => `${v}%`,
              },
            },
          }
        : {}),
    },
  };
}

export function stackedBarOptions(): ChartOptions<'bar'> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300, easing: 'easeOutQuart' },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'start',
        labels: {
          font: { family: typography.font, size: 12 },
          color: palette.axisText,
          usePointStyle: true,
          pointStyle: 'rectRounded',
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: '#1A1F25',
        titleFont: { family: typography.font, size: 13 },
        bodyFont: { family: typography.mono, size: 12 },
        cornerRadius: 8,
        padding: 10,
      },
    },
    scales: {
      x: { ...baseScale, grid: { display: false }, stacked: true },
      y: { ...baseScale, stacked: true },
    },
  };
}

export function lineOptions(): ChartOptions<'line'> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300, easing: 'easeOutQuart' },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'start',
        labels: {
          font: { family: typography.font, size: 12 },
          color: palette.axisText,
          usePointStyle: true,
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: '#1A1F25',
        titleFont: { family: typography.font, size: 13 },
        bodyFont: { family: typography.mono, size: 12 },
        cornerRadius: 8,
        padding: 10,
      },
    },
    scales: {
      x: { ...baseScale, grid: { display: false } },
      y: { ...baseScale },
    },
  };
}
