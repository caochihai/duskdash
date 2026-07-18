import { Column, Line } from '@ant-design/charts';
import { Skeleton } from 'antd';
import { EmptyState } from '@/components/common/EmptyState';
import { PageError } from '@/components/common/PageError';
import styles from './BaseChart.module.css';

export type BaseChartType = 'line' | 'column';

export interface BaseChartProps<TDatum> {
  type: BaseChartType;
  /** Dữ liệu — luôn truyền từ ngoài vào, adapter không tự chứa dữ liệu. */
  data: TDatum[];
  /**
   * Config bổ sung cho Ant Design Charts (xField, yField, axis, scale...).
   * Adapter không áp đặt cấu hình domain.
   */
  config?: Record<string, unknown>;
  height?: number;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  /** Mô tả biểu đồ cho screen reader — bắt buộc (accessibility). */
  ariaLabel: string;
  className?: string;
}

/**
 * Adapter chart tái sử dụng, dựng trên Ant Design Charts.
 *
 * Không chứa logic domain, không hard-code dữ liệu. Trang và component nghiệp vụ
 * truyền data + config qua props.
 */
export function BaseChart<TDatum>({
  type,
  data,
  config,
  height = 240,
  loading = false,
  error,
  onRetry,
  emptyTitle = 'Chưa có dữ liệu biểu đồ',
  emptyDescription = 'Dữ liệu sẽ hiển thị khi có thông tin phù hợp.',
  ariaLabel,
  className,
}: BaseChartProps<TDatum>) {
  if (loading) {
    return (
      <div className={styles.wrapper} style={{ height }} aria-busy="true" aria-label={ariaLabel}>
        <Skeleton.Node active style={{ width: '100%', height }}>
          <span />
        </Skeleton.Node>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.state} style={{ minHeight: height }}>
        <PageError
          compact
          title="Không tải được biểu đồ"
          error={error}
          onRetry={onRetry}
        />
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className={styles.state} style={{ minHeight: height }}>
        <EmptyState compact title={emptyTitle} description={emptyDescription} />
      </div>
    );
  }

  const chartProps = {
    data,
    height,
    autoFit: true,
    animate: { enter: { duration: 320 } },
    ...config,
  };

  return (
    /*
     * role="img" + aria-label: canvas của chart không tự mô tả được nội dung,
     * nên phần mô tả text là bắt buộc để screen reader hiểu được biểu đồ.
     */
    <div
      className={[styles.wrapper, styles.chart, className].filter(Boolean).join(' ')}
      role="img"
      aria-label={ariaLabel}
    >
      {type === 'line' ? <Line {...chartProps} /> : <Column {...chartProps} />}
    </div>
  );
}
