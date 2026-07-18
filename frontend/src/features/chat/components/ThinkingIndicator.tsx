import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { ThunderboltOutlined } from '@ant-design/icons';
import { AI_PHASE_LABEL, type AIProcessingPhase } from '@/types/chat';
import styles from './ThinkingIndicator.module.css';

export interface ThinkingIndicatorProps {
  phase: AIProcessingPhase | null;
}

/**
 * Trạng thái AI đang xử lý.
 *
 * CHỈ hiển thị mô tả tiến trình cấp cao ("Đang tra cứu thông tin phù hợp"),
 * không bao giờ lộ chain-of-thought nội bộ.
 */
export function ThinkingIndicator({ phase }: ThinkingIndicatorProps) {
  const prefersReducedMotion = useReducedMotion();
  const label = AI_PHASE_LABEL[phase ?? 'connecting'];

  return (
    // aria-live: screen reader thông báo khi trạng thái đổi.
    <div className={styles.wrapper} role="status" aria-live="polite">
      <span className={styles.pulseWrap}>
        {!prefersReducedMotion && (
          <motion.span
            className={styles.pulseRing}
            aria-hidden="true"
            animate={{ scale: [1, 1.35, 1], opacity: [0.65, 0, 0.65] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
        <span className={styles.pulseCore} aria-hidden="true">
          <ThunderboltOutlined />
        </span>
      </span>

      {/* Text đổi mượt bằng crossfade để không giật khi phase thay đổi. */}
      <AnimatePresence mode="wait">
        <motion.span
          key={label}
          className={styles.text}
          initial={prefersReducedMotion ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={prefersReducedMotion ? undefined : { opacity: 0, y: -4 }}
          transition={{ duration: 0.18 }}
        >
          {label}
        </motion.span>
      </AnimatePresence>

      <span className={styles.dots} aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <motion.span
            key={index}
            className={styles.dot}
            animate={prefersReducedMotion ? undefined : { opacity: [0.25, 1, 0.25] }}
            transition={{
              duration: 1.1,
              repeat: Infinity,
              delay: index * 0.16,
              ease: 'easeInOut',
            }}
          />
        ))}
      </span>
    </div>
  );
}
