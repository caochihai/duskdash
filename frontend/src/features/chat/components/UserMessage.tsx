import { motion, useReducedMotion } from 'motion/react';
import { ExclamationCircleOutlined } from '@ant-design/icons';
import { AttachmentChip } from './AttachmentChip';
import { formatTime } from '@/utils/formatDate';
import type { ChatMessage } from '@/types/chat';
import styles from './UserMessage.module.css';

export interface UserMessageProps {
  message: ChatMessage;
}

/** Tin nhắn của người dùng — canh phải, nền cam nhạt. */
export function UserMessage({ message }: UserMessageProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <motion.div
      className={styles.row}
      initial={prefersReducedMotion ? false : { opacity: 0, y: 7 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={styles.stack}>
        {message.attachments && message.attachments.length > 0 && (
          <div className={styles.attachments}>
            {message.attachments.map((attachment) => (
              <AttachmentChip key={attachment.id} attachment={attachment} readOnly />
            ))}
          </div>
        )}

        <div className={styles.bubble}>{message.content}</div>

        <div className={styles.meta}>
          {message.status === 'error' ? (
            <span className={styles.errorNote}>
              <ExclamationCircleOutlined />
              {message.errorMessage ?? 'Không gửi được tin nhắn'}
            </span>
          ) : (
            <time className={styles.time} dateTime={message.createdAt}>
              {formatTime(message.createdAt)}
            </time>
          )}
        </div>
      </div>
    </motion.div>
  );
}
