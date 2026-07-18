import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { MessageList } from './MessageList';
import { WelcomeState } from './WelcomeState';
import { ChatComposer } from './ChatComposer';
import type { ChatMessage } from '@/types/chat';
import type { ChatAttachment } from '@/types/attachment';
import type { Customer, LoanApplication, LoanApplicationStatus } from '@/types/customer';
import styles from './ChatWorkspace.module.css';

export interface ChatWorkspaceProps {
  messages: ChatMessage[];
  streamingMessage: ChatMessage | null;
  loading: boolean;
  error?: unknown;
  onRetryLoad?: () => void;

  composerValue: string;
  onComposerChange: (value: string) => void;
  onSend: (content: string, attachments: ChatAttachment[]) => void;
  onStop: () => void;
  onQuickPrompt: (prompt: string) => void;
  onRegenerate?: () => void;
  onViewSources: (message: ChatMessage) => void;

  isStreaming: boolean;
  composerDisabled?: boolean;
  /** Do ChatPage tính, để header biết nên đặt h1 ở đâu. */
  showWelcome: boolean;

  /** Tên chuyên viên đang đăng nhập — dùng cho lời chào ở Welcome State. */
  staffName?: string;
  /** Danh sách khách hàng cho lệnh `/` trong composer. */
  customers?: Customer[];
  onSelectCustomer?: (customer: Customer) => void;
  onViewCustomer?: (customerId: string) => void;
  onLoanDecision?: (
    application: LoanApplication,
    status: LoanApplicationStatus,
    note: string,
  ) => void;
  uploadContext?: { customerId?: string; loanApplicationId?: string };
}

/**
 * Vùng làm việc chính: Welcome State hoặc danh sách tin nhắn, cộng composer.
 * Composer luôn hiển thị để người dùng gõ được ở mọi trạng thái.
 */
export function ChatWorkspace({
  messages,
  streamingMessage,
  loading,
  error,
  onRetryLoad,
  composerValue,
  onComposerChange,
  onSend,
  onStop,
  onQuickPrompt,
  onRegenerate,
  onViewSources,
  isStreaming,
  composerDisabled = false,
  showWelcome,
  staffName,
  customers,
  onSelectCustomer,
  onViewCustomer,
  onLoanDecision,
  uploadContext,
}: ChatWorkspaceProps) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <div className={styles.workspace}>
      {/* Chuyển giữa Welcome State và hội thoại bằng crossfade nhẹ. */}
      <AnimatePresence mode="wait" initial={false}>
        {showWelcome ? (
          <motion.div
            key="welcome"
            className={styles.welcomeScroll}
            initial={prefersReducedMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={prefersReducedMotion ? undefined : { opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <WelcomeState onSelectPrompt={onQuickPrompt} staffName={staffName} />
          </motion.div>
        ) : (
          <motion.div
            key="conversation"
            className={styles.workspace}
            initial={prefersReducedMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.22 }}
          >
            <MessageList
              messages={messages}
              streamingMessage={streamingMessage}
              loading={loading}
              error={error}
              onRetry={onRetryLoad}
              onPrompt={onQuickPrompt}
              onRegenerate={onRegenerate}
              onViewSources={onViewSources}
              busy={isStreaming}
              onViewCustomer={onViewCustomer}
              onLoanDecision={onLoanDecision}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <ChatComposer
        value={composerValue}
        onChange={onComposerChange}
        onSend={onSend}
        onStop={onStop}
        isStreaming={isStreaming}
        disabled={composerDisabled}
        customers={customers}
        onSelectCustomer={onSelectCustomer}
        uploadContext={uploadContext}
      />
    </div>
  );
}
