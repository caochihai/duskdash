import { Button, Result } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { getErrorMessage } from '@/services/apiClient';

export interface PageErrorProps {
  title?: string;
  error?: unknown;
  /** Thông điệp tự đặt, ưu tiên hơn message suy ra từ `error`. */
  description?: string;
  onRetry?: () => void;
  retryLabel?: string;
  compact?: boolean;
}

/**
 * Error state dùng chung.
 * Không bao giờ hiển thị stack trace cho người dùng cuối.
 */
export function PageError({
  title = 'Đã có lỗi xảy ra',
  error,
  description,
  onRetry,
  retryLabel = 'Thử lại',
  compact = false,
}: PageErrorProps) {
  const message = description ?? (error ? getErrorMessage(error) : 'Vui lòng thử lại sau ít phút.');

  return (
    <Result
      status="warning"
      title={title}
      subTitle={message}
      style={compact ? { padding: '24px 16px' } : undefined}
      extra={
        onRetry && (
          <Button type="primary" icon={<ReloadOutlined />} onClick={onRetry}>
            {retryLabel}
          </Button>
        )
      }
    />
  );
}
