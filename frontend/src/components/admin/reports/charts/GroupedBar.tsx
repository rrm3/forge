import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { palette, typography, barLineOptions } from '../chartTheme';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

interface GroupedBarProps {
  title: string;
  subtitle?: string;
  categories: string[];
  weekLabels: string[];
  series: { category: string; weekly: number[] }[];
}

export function GroupedBar({ title, subtitle, categories, weekLabels, series }: GroupedBarProps) {
  const data = {
    labels: categories,
    datasets: weekLabels.map((weekLabel, wi) => ({
      label: weekLabel,
      data: series.map((s) => s.weekly[wi] || 0),
      backgroundColor: palette.barFade(wi, weekLabels.length),
      borderRadius: 4,
      barPercentage: 0.85,
    })),
  };

  const options = barLineOptions({ leftLabel: 'Mentions' });

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
