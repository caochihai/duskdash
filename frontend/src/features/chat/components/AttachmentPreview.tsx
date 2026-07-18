import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { AttachmentChip } from './AttachmentChip';
import type { ChatAttachment } from '@/types/attachment';
import styles from './AttachmentPreview.module.css';

export interface AttachmentPreviewProps {
  attachments: ChatAttachment[];
  onRemove: (id: string) => void;
  onRetry?: (id: string) => void;
}

/**
 * Danh sách tài liệu đính kèm phía trên composer.
 * Component này domain-agnostic: dữ liệu và handler đều truyền qua props.
 */
export function AttachmentPreview({ attachments, onRemove, onRetry }: AttachmentPreviewProps) {
  const prefersReducedMotion = useReducedMotion();

  if (!attachments.length) return null;

  return (
    <div className={styles.list}>
      <AnimatePresence initial={false}>
        {attachments.map((attachment) => (
          <motion.div
            key={attachment.id}
            layout={!prefersReducedMotion}
            initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.96 }}
            animate={
              // Lỗi -> lắc nhẹ một lần để thu hút chú ý, không lặp vô hạn.
              attachment.status === 'error' && !prefersReducedMotion
                ? { opacity: 1, scale: 1, x: [0, -4, 4, -2, 0] }
                : { opacity: 1, scale: 1 }
            }
            exit={prefersReducedMotion ? undefined : { opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <AttachmentChip attachment={attachment} onRemove={onRemove} onRetry={onRetry} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
