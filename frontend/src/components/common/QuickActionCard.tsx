import { createElement, type ComponentType } from 'react';
import styles from './QuickActionCard.module.css';

export interface QuickActionCardProps {
  title: string;
  description: string;
  icon: ComponentType;
  onClick: () => void;
  /** Số liệu nổi bật, ví dụ số hồ sơ đang chờ duyệt. */
  badge?: string;
}

/**
 * Thẻ gợi ý tác vụ ở Welcome State.
 * Là <button> thật để hỗ trợ bàn phím và screen reader đúng cách.
 */
export function QuickActionCard({
  title,
  description,
  icon,
  onClick,
  badge,
}: QuickActionCardProps) {
  return (
    <button type="button" className={styles.card} onClick={onClick}>
      <span className={styles.topRow}>
        <span className={styles.iconWrap} aria-hidden="true">
          {createElement(icon)}
        </span>
        {/* Badge kèm nhãn cho screen reader — con số trần không đủ ngữ nghĩa. */}
        {badge && (
          <span className={styles.badge}>
            {badge}
            <span className="sr-only"> mục đang chờ</span>
          </span>
        )}
      </span>
      <span className={styles.title}>{title}</span>
      <span className={styles.description}>{description}</span>
    </button>
  );
}
