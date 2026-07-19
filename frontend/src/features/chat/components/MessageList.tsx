import type { SourceLocator } from '@/types/source';
import type { HighlightDocument } from './HighlightDocumentViewer';
import { useEffect, useRef } from 'react';
import { Avatar, Skeleton } from 'antd';
import { MessageOutlined } from '@ant-design/icons';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { EmptyState } from '@/components/common/EmptyState';
import { PageError } from '@/components/common/PageError';
import { shbColors } from '@/theme/tokens';
import type { ChatMessage } from '@/types/chat';
import type { LoanApplication, LoanApplicationStatus } from '@/types/customer';
import styles from './MessageList.module.css';

export interface MessageListProps {
  messages: ChatMessage[];
  /** Tin nhắn AI đang được tạo (chưa nằm trong cache). */
  streamingMessage?: ChatMessage | null;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onPrompt: (prompt: string) => void;
  onRegenerate?: () => void;
  onViewSources?: (message: ChatMessage) => void;
  busy?: boolean;
  onViewCustomer?: (customerId: string) => void;
  /** Mở phiên làm việc của một khách hàng (đổi phiên chat, không chỉ mở panel). */
  onOpenCustomerSession?: (customerId: string) => void;
  onOpenLocator?: (locator: SourceLocator) => void;
  onOpenHighlightDocument?: (doc: HighlightDocument) => void;
  onLoanDecision?: (
    application: LoanApplication,
    status: LoanApplicationStatus,
    note: string,
  ) => void;
}

function MessageSkeleton() {
  return (
    <div className={styles.skeletonBlock}>
      <Skeleton.Avatar active size={30} shape="circle" />
      <div className={styles.skeletonBody}>
        <Skeleton active paragraph={{ rows: 3 }} title={{ width: '30%' }} />
      </div>
    </div>
  );
}

/**
 * Danh sách tin nhắn.
 * Domain-agnostic: mọi dữ liệu và handler đều đến từ props.
 */
export function MessageList({
  messages,
  streamingMessage,
  loading = false,
  error,
  onRetry,
  onPrompt,
  onRegenerate,
  onViewSources,
  busy = false,
  onViewCustomer,
  onOpenCustomerSession,
  onOpenLocator,
  onOpenHighlightDocument,
  onLoanDecision,
}: MessageListProps) {
  const anchorRef = useRef<HTMLDivElement>(null);

  // Cuộn xuống cuối khi có tin nhắn mới hoặc nội dung stream dài thêm.
  useEffect(() => {
    anchorRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, streamingMessage?.content, streamingMessage?.status]);

  if (loading) {
    return (
      <div className={styles.scroll}>
        <div className={styles.inner} aria-busy="true">
          <MessageSkeleton />
          <MessageSkeleton />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.scroll}>
        <div className={styles.stateWrap}>
          <PageError
            title="Không tải được nội dung cuộc trò chuyện"
            error={error}
            onRetry={onRetry}
          />
        </div>
      </div>
    );
  }

  if (!messages.length && !streamingMessage) {
    return (
      <div className={styles.scroll}>
        <div className={styles.stateWrap}>
          <EmptyState
            image={
              <Avatar
                size={48}
                icon={<MessageOutlined />}
                style={{ background: shbColors.orange[50], color: shbColors.orange[500] }}
              />
            }
            title="Cuộc trò chuyện này chưa có nội dung"
            description="Hãy bắt đầu bằng một câu hỏi dành cho SH-AI."
          />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.scroll}>
      <div className={styles.inner}>
        {messages.map((message) =>
          message.role === 'user' ? (
            <UserMessage key={message.id} message={message} />
          ) : (
            <AssistantMessage
              key={message.id}
              message={message}
              onPrompt={onPrompt}
              onRegenerate={onRegenerate}
              onViewSources={onViewSources}
              busy={busy}
              onViewCustomer={onViewCustomer}
              onOpenCustomerSession={onOpenCustomerSession}
              onOpenLocator={onOpenLocator}
              onOpenHighlightDocument={onOpenHighlightDocument}
              onLoanDecision={onLoanDecision}
            />
          ),
        )}

        {streamingMessage && (
          <AssistantMessage
            key={streamingMessage.id}
            message={streamingMessage}
            onPrompt={onPrompt}
            busy
          />
        )}

        <div ref={anchorRef} className={styles.anchor} />
      </div>
    </div>
  );
}
