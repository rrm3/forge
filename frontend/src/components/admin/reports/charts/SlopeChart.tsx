import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { palette, typography, lineOptions } from '../chartTheme';

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

interface SlopeChartProps {
  title: string;
  subtitle?: string;
  labels: string[];
  departments: { name: string; data: number[] }[];
}

export function SlopeChart({ title, subtitle, labels, departments }: SlopeChartProps) {
  const sorted = [...departments].sort(
    (a, b) => (b.data[b.data.length - 1] || 0) - (a.data[a.data.length - 1] || 0)
  );
  const top = sorted.slice(0, 8);

  const data = {
    labels,
    datasets: top.map((dept, i) => ({
      label: dept.name,
      data: dept.data,
      borderColor: palette.departmentColors[i % palette.departmentColors.length],
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: '#FFFFFF',
      pointBorderColor: palette.departmentColors[i % palette.departmentColors.length],
      pointBorderWidth: 2,
      tension: 0,
    })),
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
      <div style={{ height: 360, marginTop: 16 }}>
        <Line data={data} options={lineOptions() as any} />
      </div>
    </div>
  );
}
