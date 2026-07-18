import { Empty, Typography } from 'antd';
import type { ReactNode } from 'react';

const { Text } = Typography;

export interface EmptyStateProps {
  title: string;
  description?: string;
  /** Ảnh/icon tuỳ chọn. Mặc định dùng Empty đơn giản của Ant Design. */
  image?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}

/** Empty state dùng chung — nội dung tiếng Việt, không lorem ipsum. */
export function EmptyState({ title, description, image, action, compact = false }: EmptyStateProps) {
  return (
    <Empty
      image={image ?? Empty.PRESENTED_IMAGE_SIMPLE}
      styles={{ image: { height: compact ? 44 : 62, marginBottom: compact ? 8 : 12 } }}
      description={
        <span>
          <Text strong style={{ display: 'block', marginBottom: description ? 4 : 0 }}>
            {title}
          </Text>
          {description && (
            <Text type="secondary" style={{ fontSize: 13 }}>
              {description}
            </Text>
          )}
        </span>
      }
    >
      {action}
    </Empty>
  );
}
