import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { palette, typography } from '../chartTheme';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface SentimentWeek {
  week: number;
  excited: number;
  positive: number;
  neutral: number;
  mixed: number;
  frustrated: number;
  has_data?: boolean;
}

interface DivergingStackedBarProps {
  title: string;
  subtitle?: string;
  labels: string[];
  sentimentData: SentimentWeek[];
}

export function DivergingStackedBar({ title, subtitle, labels, sentimentData }: DivergingStackedBarProps) {
  const normalized = sentimentData.map((s) => {
    const total = s.excited + s.positive + s.neutral + s.mixed + s.frustrated;
    if (total === 0) return { ...s, excited: 0, positive: 0, neutral: 0, mixed: 0, frustrated: 0, _total: 0 };
    return {
      excited: Math.round((s.excited / total) * 100),
      positive: Math.round((s.positive / total) * 100),
      neutral: Math.round((s.neutral / total) * 100),
      mixed: -Math.round((s.mixed / total) * 100),
      frustrated: -Math.round((s.frustrated / total) * 100),
      _total: total,
      week: s.week,
    };
  });

  const data = {
    labels,
    datasets: [
      { label: 'Excited', data: normalized.map((d) => d.excited), backgroundColor: palette.sentiment.excited, stack: 'positive', borderRadius: 2, barPercentage: 0.85 },
      { label: 'Positive', data: normalized.map((d) => d.positive), backgroundColor: palette.sentiment.positive, stack: 'positive', borderRadius: 2, barPercentage: 0.85 },
      { label: 'Neutral', data: normalized.map((d) => d.neutral), backgroundColor: palette.sentiment.neutral, stack: 'positive', borderRadius: 2, barPercentage: 0.85 },
      { label: 'Mixed', data: normalized.map((d) => d.mixed), backgroundColor: palette.sentiment.mixed, stack: 'negative', borderRadius: 2, barPercentage: 0.85 },
      { label: 'Frustrated', data: normalized.map((d) => d.frustrated), backgroundColor: palette.sentiment.frustrated, stack: 'negative', borderRadius: 2, barPercentage: 0.85 },
    ],
  };

  const noDataIndices = sentimentData
    .map((s, i) => (s.has_data === false || (s.excited + s.positive + s.neutral + s.mixed + s.frustrated) === 0) ? i : -1)
    .filter((i) => i >= 0);

  const noDataPlugin = {
    id: 'noDataLabels',
    afterDraw(chart: any) {
      const { ctx, scales } = chart;
      const xScale = scales.x;
      const yScale = scales.y;
      if (!xScale || !yScale) return;
      ctx.save();
      ctx.font = `italic 12px ${typography.font}`;
      ctx.fillStyle = '#94A3B8';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      for (const idx of noDataIndices) {
        const x = xScale.getPixelForValue(idx);
        const y = yScale.getPixelForValue(0);
        ctx.fillText('No data', x, y);
      }
      ctx.restore();
    },
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300, easing: 'easeOutQuart' as const },
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: {
        position: 'top' as const,
        align: 'start' as const,
        labels: {
          font: { family: typography.font, size: 12 },
          color: palette.axisText,
          usePointStyle: true,
          pointStyle: 'rectRounded' as const,
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: '#1A1F25',
        titleFont: { family: typography.font, size: 13 },
        bodyFont: { family: typography.mono, size: 12 },
        cornerRadius: 8,
        padding: 10,
        callbacks: {
          label: (ctx: any) => `${ctx.dataset.label}: ${Math.abs(ctx.raw)}%`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { family: typography.mono, size: 12 }, color: palette.axisText },
        stacked: true,
      },
      y: {
        grid: { color: palette.gridline },
        ticks: {
          font: { family: typography.mono, size: 12 },
          color: palette.axisText,
          callback: (v: unknown) => `${Math.abs(Number(v))}%`,
        },
        stacked: true,
      },
    },
  };

  return (
    <div style={{
      backgroundColor: palette.cardBg,
      border: `1px solid ${palette.cardBorder}`,
      borderRadius: 14,
      padding: 24,
    }}>
      <h3 style={{ fontSize: 20, fontWeight: 600, fontFamily: typography.font, color: '#1A1F25', margin: 0 }}>
        {title}
      </h3>
      {subtitle && (
        <p style={{ fontSize: 14, fontFamily: typography.font, color: '#64748B', margin: '4px 0 0' }}>
          {subtitle}
        </p>
      )}
      <div style={{ height: 320, marginTop: 16 }}>
        <Bar data={data} options={options as any} plugins={[noDataPlugin]} />
      </div>
    </div>
  );
}
