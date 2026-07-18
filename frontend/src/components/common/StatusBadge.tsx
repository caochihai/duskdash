import styles from './StatusBadge.module.css';

export type StatusTone = 'online' | 'busy' | 'offline';

export interface StatusBadgeProps {
  tone?: StatusTone;
  label: string;
  pulse?: boolean;
}

const TONE_CLASS: Record<StatusTone, string> = {
  online: styles.online,
  busy: styles.busy,
  offline: styles.offline,
};

/**
 * Badge trạng thái.
 * Luôn kèm nhãn chữ — không dùng riêng màu sắc làm tín hiệu (accessibility).
 */
export function StatusBadge({ tone = 'online', label, pulse = true }: StatusBadgeProps) {
  return (
    <span className={[styles.badge, TONE_CLASS[tone]].join(' ')}>
      <span
        className={[styles.dot, pulse && tone === 'online' ? styles.dotPulse : '']
          .filter(Boolean)
          .join(' ')}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
