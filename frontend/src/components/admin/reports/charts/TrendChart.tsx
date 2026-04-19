import { useRef, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  LineController,
  BarController,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';
import { palette, typography, barLineOptions } from '../chartTheme';

ChartJS.register(
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  LineController, BarController, Tooltip, Legend, Filler,
);

interface SummaryTile {
  label: string;
  value: string | number;
  sub?: string;
}

interface TrendChartProps {
  title: string;
  subtitle?: string;
  labels: string[];
  barData: number[];
  barLabel?: string;
  lineData?: number[];
  lineLabel?: string;
  leftAxisLabel?: string;
  rightAxisLabel?: string;
  summaryTiles?: SummaryTile[];
}

export function TrendChart({
  title,
  subtitle,
  labels,
  barData,
  barLabel = 'Count',
  lineData,
  lineLabel = '%',
  leftAxisLabel,
  rightAxisLabel,
  summaryTiles,
}: TrendChartProps) {
  const total = labels.length;

  const data = {
    labels,
    datasets: [
      {
        type: 'bar' as const,
        label: barLabel,
        data: barData,
        backgroundColor: labels.map((_, i) => palette.barFade(i, total)),
        borderRadius: 4,
        borderSkipped: 'bottom' as const,
        barPercentage: 0.85,
        yAxisID: 'y',
        order: 2,
      },
      ...(lineData
        ? [{
            type: 'line' as const,
            label: lineLabel,
            data: lineData,
            borderColor: palette.lineAccent,
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointBackgroundColor: '#FFFFFF',
            pointBorderColor: palette.lineAccent,
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
            yAxisID: rightAxisLabel ? 'y1' : 'y',
            order: 1,
            tension: 0,
          }]
        : []),
    ],
  };

  const options = barLineOptions({
    leftLabel: leftAxisLabel,
    rightLabel: rightAxisLabel,
  });

  return (
    <div style={{
      backgroundColor: palette.cardBg,
      border: `1px solid ${palette.cardBorder}`,
      borderRadius: 14,
      padding: 24,
    }}>
      <h3 style={{
        fontSize: 20,
        fontWeight: 600,
        fontFamily: typography.font,
        color: '#1A1F25',
        margin: 0,
      }}>
        {title}
      </h3>
      {subtitle && (
        <p style={{
          fontSize: 14,
          fontFamily: typography.font,
          color: '#64748B',
          margin: '4px 0 0',
        }}>
          {subtitle}
        </p>
      )}
      <div style={{ height: 320, marginTop: 16 }}>
        <Chart type="bar" data={data} options={options as any} />
      </div>
      {summaryTiles && summaryTiles.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${summaryTiles.length}, 1fr)`,
          gap: 16,
          marginTop: 16,
        }}>
          {summaryTiles.map((tile) => (
            <div
              key={tile.label}
              style={{
                backgroundColor: '#FFFFFF',
                border: `1px solid ${palette.cardBorder}`,
                borderRadius: 10,
                padding: '12px 16px',
                textAlign: 'center',
              }}
            >
              <div style={{
                fontSize: 11,
                fontWeight: 500,
                fontFamily: typography.font,
                color: '#64748B',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}>
                {tile.label}
              </div>
              <div style={{
                fontSize: 24,
                fontWeight: 600,
                fontFamily: typography.mono,
                color: '#1A1F25',
                fontVariantNumeric: 'tabular-nums',
                marginTop: 4,
              }}>
                {tile.value}
              </div>
              {tile.sub && (
                <div style={{
                  fontSize: 12,
                  fontWeight: 500,
                  fontFamily: typography.font,
                  color: '#64748B',
                  marginTop: 2,
                }}>
                  {tile.sub}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
