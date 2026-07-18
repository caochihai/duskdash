import { motion, useReducedMotion } from 'motion/react';
import { AnimatedSHBLogo } from './AnimatedSHBLogo';
import styles from './LoadingScreen.module.css';

export interface LoadingScreenProps {
  message?: string;
  /** `inline` dùng cho Suspense fallback trong trang, không phủ toàn màn hình. */
  inline?: boolean;
}

/**
 * Màn hình khởi tạo ứng dụng.
 * Không cố tình delay — chỉ hiển thị khi thực sự đang chờ.
 */
export function LoadingScreen({ message = 'Đang khởi tạo SH-AI', inline = false }: LoadingScreenProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      className={[styles.screen, inline ? styles.inline : ''].filter(Boolean).join(' ')}
      role="status"
      aria-live="polite"
    >
      <AnimatedSHBLogo size="large" glow animated={!prefersReducedMotion} />

      <motion.p
        className={styles.message}
        initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.28, duration: 0.3 }}
      >
        {message}
      </motion.p>

      <div className={styles.track} aria-hidden="true">
        <motion.div
          className={styles.bar}
          initial={{ x: '-100%' }}
          animate={prefersReducedMotion ? { x: '0%' } : { x: ['-100%', '250%'] }}
          transition={
            prefersReducedMotion
              ? { duration: 0 }
              : { duration: 1.1, repeat: Infinity, ease: 'easeInOut' }
          }
        />
      </div>
    </div>
  );
}
