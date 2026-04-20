import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { palette, typography } from '../chartTheme';

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, Tooltip);

interface Sparkline {
  label: string;
  data: number[];
  current: string;
}

interface SparklineRowProps {
  sparklines: Sparkline[];
  weekLabels: string[];
}

export function SparklineRow({ sparklines, weekLabels }: SparklineRowProps) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${sparklines.length}, 1fr)`,
      gap: 16,
    }}>
      {sparklines.map((sp) => (
        <div
          key={sp.label}
          style={{
            backgroundColor: palette.cardBg,
            border: `1px solid ${palette.cardBorder}`,
            borderRadius: 14,
            padding: '16px 20px',
          }}
        >
          <div style={{ fontSize: 12, fontWeight: 500, fontFamily: typography.font, color: '#64748B' }}>
            {sp.label}
          </div>
          <div style={{
            fontSize: 24,
            fontWeight: 600,
            fontFamily: typography.mono,
            color: '#1A1F25',
            fontVariantNumeric: 'tabular-nums',
            margin: '4px 0 8px',
          }}>
            {sp.current}
          </div>
          <div style={{ height: 40 }}>
            <Line
              data={{
                labels: weekLabels,
                datasets: [{
                  data: sp.data,
                  borderColor: palette.barPrimary,
                  borderWidth: 2,
                  pointRadius: 0,
                  tension: 0,
                  fill: false,
                }],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                  x: { display: false },
                  y: { display: false },
                },
                animation: { duration: 0 },
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
