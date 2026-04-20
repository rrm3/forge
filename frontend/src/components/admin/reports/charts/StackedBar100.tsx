import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { palette, typography, stackedBarOptions } from '../chartTheme';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface StackedBar100Props {
  title: string;
  subtitle?: string;
  labels: string[];
  series: { label: string; data: number[]; color: string }[];
  normalize?: boolean;
}

export function StackedBar100({ title, subtitle, labels, series, normalize = true }: StackedBar100Props) {
  let processedSeries = series;

  if (normalize) {
    const totals = labels.map((_, i) =>
      series.reduce((sum, s) => sum + (s.data[i] || 0), 0)
    );
    processedSeries = series.map((s) => ({
      ...s,
      data: s.data.map((v, i) => (totals[i] > 0 ? Math.round((v / totals[i]) * 100) : 0)),
    }));
  }

  const data = {
    labels,
    datasets: processedSeries.map((s) => ({
      label: s.label,
      data: s.data,
      backgroundColor: s.color,
      borderRadius: 2,
      borderSkipped: false as const,
      barPercentage: 0.85,
    })),
  };

  const options = {
    ...stackedBarOptions(),
    plugins: {
      ...stackedBarOptions().plugins,
      tooltip: {
        ...stackedBarOptions().plugins?.tooltip,
        callbacks: normalize ? {
          label: (ctx: any) => {
            const pct = ctx.raw;
            const raw = series[ctx.datasetIndex]?.data[ctx.dataIndex] ?? 0;
            return `${ctx.dataset.label}: ${raw} (${pct}%)`;
          },
        } : undefined,
      },
    },
    scales: {
      ...stackedBarOptions().scales,
      y: {
        ...stackedBarOptions().scales?.y,
        max: normalize ? 100 : undefined,
        ticks: {
          font: { family: typography.mono, size: 12 },
          color: palette.axisText,
          callback: normalize ? (v: unknown) => `${v}%` : undefined,
        },
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
        <Bar data={data} options={options as any} />
      </div>
    </div>
  );
}
