import { motion, useReducedMotion } from 'motion/react';
import { SHBLogo, type SHBLogoProps } from './SHBLogo';
import styles from './AnimatedSHBLogo.module.css';

export interface AnimatedSHBLogoProps {
  variant?: SHBLogoProps['variant'];
  size?: SHBLogoProps['size'];
  animated?: boolean;
  showProductName?: boolean;
  /** Glow cam phía sau logo. */
  glow?: boolean;
  glowIntensity?: 'subtle' | 'normal';
  className?: string;
}

/**
 * Logo SHB có hiệu ứng xuất hiện.
 *
 * Nguyên tắc thương hiệu: CHỈ animate container và lớp glow.
 * Không xoay, không bóp méo, không tách phần, không đổi màu logo.
 */
export function AnimatedSHBLogo({
  variant = 'default',
  size = 'medium',
  animated = true,
  showProductName = false,
  glow = false,
  glowIntensity = 'normal',
  className,
}: AnimatedSHBLogoProps) {
  const prefersReducedMotion = useReducedMotion();
  const shouldAnimate = animated && !prefersReducedMotion;

  return (
    <motion.span
      className={[styles.wrapper, className].filter(Boolean).join(' ')}
      initial={shouldAnimate ? { opacity: 0, y: 10 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
    >
      {glow && (
        <motion.span
          aria-hidden="true"
          className={[styles.glow, glowIntensity === 'subtle' ? styles.glowSubtle : '']
            .filter(Boolean)
            .join(' ')}
          initial={shouldAnimate ? { opacity: 0, scale: 0.82 } : false}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.1, ease: 'easeOut' }}
        />
      )}

      <SHBLogo variant={variant} size={size} showProductName={showProductName} />
    </motion.span>
  );
}
