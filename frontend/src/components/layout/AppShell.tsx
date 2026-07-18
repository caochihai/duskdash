import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { shbLayout } from '@/theme/tokens';
import styles from './AppShell.module.css';

export interface AppShellProps {
  sidebar: ReactNode;
  header: ReactNode;
  children: ReactNode;
  sidebarCollapsed: boolean;
}

/**
 * Khung ứng dụng: sidebar cố định + vùng chat cuộn độc lập.
 * Chiếm trọn viewport, không tạo scrollbar thứ hai.
 */
export function AppShell({ sidebar, header, children, sidebarCollapsed }: AppShellProps) {
  const prefersReducedMotion = useReducedMotion();

  const width = sidebarCollapsed ? shbLayout.sidebarCollapsedWidth : shbLayout.sidebarWidth;

  return (
    <div className={styles.shell}>
      <motion.aside
        className={styles.sider}
        // Animate width để đóng/mở sidebar mượt, không nhảy layout.
        animate={{ width }}
        initial={false}
        transition={
          prefersReducedMotion ? { duration: 0 } : { duration: 0.26, ease: [0.22, 1, 0.36, 1] }
        }
        aria-label="Danh sách cuộc trò chuyện"
      >
        {sidebar}
      </motion.aside>

      <div className={styles.main}>
        {header}
        <main id="main-content" className={styles.content}>
          {children}
        </main>
      </div>
    </div>
  );
}
