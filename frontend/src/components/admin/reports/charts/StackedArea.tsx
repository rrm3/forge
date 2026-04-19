import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { palette, typography, lineOptions } from '../chartTheme';

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Filler, Tooltip, Legend);

interface StackedAreaProps {
  title: string;
  subtitle?: string;
  labels: string[];
  series: { label: string; data: number[]; color: string }[];
}

export function StackedArea({ title, subtitle, labels, series }: StackedAreaProps) {
  const data = {
    labels,
    datasets: series.map((s, i) => ({
      label: s.label,
      data: s.data,
      borderColor: s.color,
      backgroundColor: s.color + '40',
      fill: i === 0 ? 'origin' : '-1',
      borderWidth: 2,
      pointRadius: 3,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: s.color,
      pointBorderWidth: 2,
      tension: 0,
    })),
  };

  const options = {
    ...lineOptions(),
    scales: {
      ...lineOptions().scales,
      y: {
        ...lineOptions().scales?.y,
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
        <Line data={data} options={options as any} />
      </div>
    </div>
  );
}
