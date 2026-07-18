import { useMemo } from 'react';
import { BaseChart } from './BaseChart';
import { shbChartPalette } from './chartPalette';
import { formatCompactVnd, formatCurrency } from '@/utils/formatCurrency';
import type { ChartBlock, ChartDatum } from '@/types/chat';

export interface LoanBreakdownChartProps {
  data: ChartDatum[];
  chartType?: ChartBlock['chartType'];
  valueFormat?: ChartBlock['valueFormat'];
  height?: number;
  /** Mô tả dùng cho screen reader. */
  description?: string;
}

/**
 * Biểu đồ cơ cấu khoản vay (gốc / lãi / tổng).
 *
 * Là lớp domain mỏng bọc quanh `BaseChart` — page không gọi thẳng thư viện chart.
 */
export function LoanBreakdownChart({
  data,
  chartType = 'column',
  valueFormat = 'currency',
  height = 240,
  description,
}: LoanBreakdownChartProps) {
  const formatValue = useMemo(
    () => (value: number) => {
      if (valueFormat === 'currency') return formatCurrency(value);
      if (valueFormat === 'percent') return `${value}%`;
      return String(value);
    },
    [valueFormat],
  );

  const config = useMemo(
    () => ({
      xField: 'category',
      yField: 'value',
      colorField: 'category',
      scale: {
        color: { range: shbChartPalette },
      },
      axis: {
        y: {
          labelFormatter: (value: number) =>
            valueFormat === 'currency' ? formatCompactVnd(value) : String(value),
        },
        x: {
          labelAutoRotate: false,
        },
      },
      legend: false,
      style: {
        radiusTopLeft: 6,
        radiusTopRight: 6,
        maxWidth: 64,
      },
      tooltip: {
        title: (datum: ChartDatum) => datum.category,
        items: [
          {
            channel: 'y' as const,
            valueFormatter: (value: number) => formatValue(value),
          },
        ],
      },
    }),
    [formatValue, valueFormat],
  );

  // Mô tả text để screen reader nắm được nội dung biểu đồ.
  const ariaLabel =
    description ??
    `Biểu đồ cột: ${data.map((item) => `${item.category} ${formatValue(item.value)}`).join(', ')}.`;

  return (
    <BaseChart<ChartDatum>
      type={chartType}
      data={data}
      config={config}
      height={height}
      ariaLabel={ariaLabel}
      emptyTitle="Chưa có dữ liệu để hiển thị biểu đồ"
    />
  );
}
