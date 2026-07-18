import { motion, useReducedMotion } from 'motion/react';
import { shbColors } from '@/theme/tokens';
import styles from './SHBAmbientBackground.module.css';

/**
 * Nền trang trí cho Welcome State.
 *
 * Ràng buộc: không chặn click, không che chữ, không gây overflow,
 * không dùng video/WebGL, tự tắt chuyển động khi người dùng bật reduced motion.
 */
export function SHBAmbientBackground() {
  const prefersReducedMotion = useReducedMotion();

  const floatTransition = prefersReducedMotion
    ? undefined
    : { duration: 18, repeat: Infinity, ease: 'easeInOut' as const };

  return (
    <div className={styles.background} aria-hidden="true">
      <motion.span
        className={[styles.orb, styles.orbOne].join(' ')}
        animate={prefersReducedMotion ? undefined : { y: [0, 18, 0], x: [0, -12, 0] }}
        transition={floatTransition}
      />
      <motion.span
        className={[styles.orb, styles.orbTwo].join(' ')}
        animate={prefersReducedMotion ? undefined : { y: [0, -14, 0], x: [0, 10, 0] }}
        transition={floatTransition ? { ...floatTransition, duration: 22 } : undefined}
      />

      {/* Đường cong mềm — gợi tinh thần "đồng hành" của thương hiệu. */}
      <svg
        className={styles.curve}
        viewBox="0 0 600 260"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        focusable="false"
      >
        <path
          d="M0 210C120 210 168 34 300 34C432 34 480 210 600 210"
          stroke="url(#shb-ambient-curve)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <defs>
          <linearGradient id="shb-ambient-curve" x1="0" y1="0" x2="600" y2="0">
            <stop stopColor={shbColors.orange[500]} stopOpacity="0" />
            <stop offset="0.5" stopColor={shbColors.orange[500]} stopOpacity="0.32" />
            <stop offset="1" stopColor={shbColors.orange[500]} stopOpacity="0" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}
