import { motion, useReducedMotion } from 'motion/react';
import { AnimatedSHBLogo } from '@/components/common/AnimatedSHBLogo';
import { QuickActionCard } from '@/components/common/QuickActionCard';
import { SHBAmbientBackground } from './SHBAmbientBackground';
import { QUICK_PROMPTS } from '@/features/chat/constants/quickPrompts';
import styles from './WelcomeState.module.css';

export interface WelcomeStateProps {
  /** Được gọi khi chuyên viên chọn một thẻ gợi ý. */
  onSelectPrompt: (prompt: string) => void;
  /** Tên chuyên viên đang đăng nhập — lời chào cá nhân hoá. */
  staffName?: string;
}

/** Lấy tên riêng (từ cuối) cho lời chào tự nhiên trong tiếng Việt. */
function getGivenName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  return parts.length > 1 ? parts.slice(-2).join(' ') : fullName;
}

/**
 * Màn hình chào khi hội thoại chưa có tin nhắn.
 * Thứ tự xuất hiện: logo -> heading -> mô tả -> quick cards (stagger).
 */
export function WelcomeState({ onSelectPrompt, staffName }: WelcomeStateProps) {
  const prefersReducedMotion = useReducedMotion();

  const fadeUp = (delay: number) =>
    prefersReducedMotion
      ? {}
      : {
          initial: { opacity: 0, y: 12 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] as const },
        };

  return (
    <div className={styles.wrapper}>
      <SHBAmbientBackground />

      <div className={styles.inner}>
        <div className={styles.logoBlock}>
          <AnimatedSHBLogo size="large" glow glowIntensity="normal" />
        </div>

        <motion.h1 className={styles.heading} {...fadeUp(0.1)}>
          {staffName ? (
            <>
              Xin chào, <span className={styles.headingAccent}>{getGivenName(staffName)}</span>
            </>
          ) : (
            <>
              Hệ chuyên gia số <span className={styles.headingAccent}>SH-AI</span>
            </>
          )}
        </motion.h1>

        <motion.p className={styles.description} {...fadeUp(0.18)}>
          Đội ngũ chuyên gia số về tín dụng, pháp chế, sản phẩm và vận hành
          <br />
          sẵn sàng phối hợp xử lý yêu cầu của bạn.
        </motion.p>

        <div className={styles.grid}>
          {QUICK_PROMPTS.map((item, index) => (
            <motion.div
              key={item.id}
              {...(prefersReducedMotion
                ? {}
                : {
                    initial: { opacity: 0, y: 14 },
                    animate: { opacity: 1, y: 0 },
                    transition: {
                      duration: 0.34,
                      // Stagger: mỗi thẻ trễ thêm 60ms.
                      delay: 0.26 + index * 0.06,
                      ease: [0.22, 1, 0.36, 1] as const,
                    },
                  })}
            >
              <QuickActionCard
                title={item.title}
                description={item.description}
                icon={item.icon}
                badge={item.badge}
                onClick={() => onSelectPrompt(item.prompt)}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
