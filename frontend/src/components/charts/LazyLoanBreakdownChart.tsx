import { lazy, Suspense } from 'react';
import { Skeleton } from 'antd';
import type { LoanBreakdownChartProps } from './LoanBreakdownChart';

/**
 * Ant Design Charts là thư viện nặng (~1.4 MB). Chỉ một phần nhỏ câu trả lời có
 * biểu đồ, nên chart được tách khỏi bundle khởi động và chỉ tải khi thực sự cần.
 */
const LoanBreakdownChart = lazy(() =>
  import('./LoanBreakdownChart').then((module) => ({ default: module.LoanBreakdownChart })),
);

export function LazyLoanBreakdownChart(props: LoanBreakdownChartProps) {
  return (
    <Suspense
      fallback={
        <Skeleton.Node active style={{ width: '100%', height: props.height ?? 240 }}>
          <span />
        </Skeleton.Node>
      }
    >
      <LoanBreakdownChart {...props} />
    </Suspense>
  );
}
