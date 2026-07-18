import { lazy, Suspense } from 'react';
import { Skeleton } from 'antd';
import type { BaseChartProps } from './BaseChart';

/**
 * Wrapper lazy cho `BaseChart` generic.
 *
 * Ant Design Charts nặng ~1,4 MB nên chỉ tải khi thực sự có biểu đồ cần vẽ.
 */
const BaseChart = lazy(() =>
  import('./BaseChart').then((module) => ({
    default: module.BaseChart as unknown as React.ComponentType<BaseChartProps<unknown>>,
  })),
);

export function LazyBaseChart<TDatum>(props: BaseChartProps<TDatum>) {
  return (
    <Suspense
      fallback={
        <Skeleton.Node active style={{ width: '100%', height: props.height ?? 240 }}>
          <span />
        </Skeleton.Node>
      }
    >
      <BaseChart {...(props as BaseChartProps<unknown>)} />
    </Suspense>
  );
}
