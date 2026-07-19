import { useState } from 'react';
import { App, Alert, Button, Image, Tooltip } from 'antd';
import {
  BookOutlined,
  CopyOutlined,
  DislikeFilled,
  DislikeOutlined,
  LikeFilled,
  LikeOutlined,
  ReloadOutlined,
  ShareAltOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { MarkdownContent } from './MarkdownContent';
import type { HighlightDocument } from './HighlightDocumentViewer';
import { MessageBlocks } from './MessageBlocks';
import { SuggestedQuestions } from './SuggestedQuestions';
import { ThinkingIndicator } from './ThinkingIndicator';
import { AgentTrace } from './AgentTrace';
import type { ChatMessage, MessageFeedback } from '@/types/chat';
import type { LoanApplication, LoanApplicationStatus } from '@/types/customer';
import styles from './AssistantMessage.module.css';

export interface AssistantMessageProps {
  message: ChatMessage;
  onPrompt: (prompt: string) => void;
  onRegenerate?: () => void;
  onViewSources?: (message: ChatMessage) => void;
  /** Có tin nhắn khác đang được tạo -> khoá các action gửi. */
  busy?: boolean;
  onViewCustomer?: (customerId: string) => void;
  /** Bấm thumbnail/dẫn chứng -> mở viewer ở panel phải, khoanh đúng vùng. */
  onOpenHighlightDocument?: (doc: HighlightDocument) => void;
  onLoanDecision?: (
    application: LoanApplication,
    status: LoanApplicationStatus,
    note: string,
  ) => void;
}

/** Tin nhắn của SH-AI — canh trái, không bubble nặng, tối ưu cho văn bản dài. */
export function AssistantMessage({
  message,
  onPrompt,
  onRegenerate,
  onViewSources,
  busy = false,
  onViewCustomer,
  onOpenHighlightDocument,
  onLoanDecision,
}: AssistantMessageProps) {
  const { message: messageApi } = App.useApp();
  const prefersReducedMotion = useReducedMotion();
  const [feedback, setFeedback] = useState<MessageFeedback | null>(null);

  const isThinking = message.status === 'thinking';
  const isStreaming = message.status === 'streaming';
  const isError = message.status === 'error';
  const isStopped = message.status === 'stopped';
  const isComplete = message.status === 'completed';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      messageApi.success('Đã sao chép câu trả lời');
    } catch {
      messageApi.error('Không sao chép được. Vui lòng thử lại.');
    }
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      messageApi.success('Đã sao chép nội dung để chia sẻ');
    } catch {
      messageApi.error('Không chia sẻ được. Vui lòng thử lại.');
    }
  };

  const handleFeedback = (value: MessageFeedback) => {
    const next = feedback === value ? null : value;
    setFeedback(next);
    if (next) {
      messageApi.success('Cảm ơn bạn đã phản hồi');
    }
  };

  return (
    <motion.div
      className={styles.row}
      initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
    >
      <span className={styles.avatar} aria-hidden="true">
        <ThunderboltOutlined />
      </span>

      <div className={styles.body}>
        <span className={styles.name}>SH-AI</span>

        {/*
          Agent trace đứng TRƯỚC nội dung: chuyên viên thấy hệ chuyên gia số đã
          làm gì rồi mới đọc kết luận — giống trình tự thẩm định thực tế.
        */}
        {message.trace && (
          <AgentTrace trace={message.trace} running={isThinking || isStreaming} />
        )}

        {isThinking && <ThinkingIndicator phase={message.phase ?? 'connecting'} />}

        {isStreaming && (
          <p className={styles.streamingText}>
            {message.content}
            <span className={styles.cursor} aria-hidden="true" />
          </p>
        )}

        {isError && (
          <Alert
            type="error"
            showIcon
            message="Không tạo được câu trả lời"
            description={message.errorMessage ?? 'Vui lòng thử lại sau ít phút.'}
            action={
              onRegenerate && (
                <Button size="small" icon={<ReloadOutlined />} onClick={onRegenerate}>
                  Thử lại
                </Button>
              )
            }
          />
        )}

        {isStopped && (
          <>
            {/* Có thể dừng khi chưa stream chữ nào -> chỉ hiện phần text nếu có. */}
            {message.content.trim() && (
              <p className={styles.streamingText}>{message.content}</p>
            )}
            <span className={styles.stoppedNote}>
              {message.content.trim()
                ? 'Đã dừng tạo câu trả lời'
                : 'Đã dừng tạo câu trả lời trước khi có nội dung'}
            </span>
          </>
        )}

        {isComplete &&
          (message.blocks?.length ? (
            <MessageBlocks
              blocks={message.blocks}
              onPrompt={onPrompt}
              disabled={busy}
              onViewCustomer={onViewCustomer}
              onLoanDecision={onLoanDecision}
            />
          ) : (
            <MarkdownContent content={message.content} />
          ))}

        {(isComplete || isStopped) && (
          <div className={styles.actions}>
            <Tooltip title="Sao chép">
              <Button type="text" size="small" icon={<CopyOutlined />} onClick={handleCopy} aria-label="Sao chép câu trả lời" />
            </Tooltip>

            <Tooltip title="Hữu ích">
              <Button
                type="text"
                size="small"
                icon={feedback === 'helpful' ? <LikeFilled /> : <LikeOutlined />}
                onClick={() => handleFeedback('helpful')}
                aria-label="Đánh giá câu trả lời hữu ích"
                aria-pressed={feedback === 'helpful'}
              />
            </Tooltip>

            <Tooltip title="Chưa hữu ích">
              <Button
                type="text"
                size="small"
                icon={feedback === 'not-helpful' ? <DislikeFilled /> : <DislikeOutlined />}
                onClick={() => handleFeedback('not-helpful')}
                aria-label="Đánh giá câu trả lời chưa hữu ích"
                aria-pressed={feedback === 'not-helpful'}
              />
            </Tooltip>

            {onRegenerate && (
              <Tooltip title="Tạo lại">
                <Button
                  type="text"
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={onRegenerate}
                  disabled={busy}
                  aria-label="Tạo lại câu trả lời"
                />
              </Tooltip>
            )}

            <Tooltip title="Chia sẻ">
              <Button type="text" size="small" icon={<ShareAltOutlined />} onClick={handleShare} aria-label="Chia sẻ câu trả lời" />
            </Tooltip>

            {message.sources && message.sources.length > 0 && onViewSources && (
              <Tooltip title="Xem nguồn">
                <Button
                  type="text"
                  size="small"
                  icon={<BookOutlined />}
                  onClick={() => onViewSources(message)}
                  aria-label={`Xem ${message.sources.length} nguồn tham khảo`}
                >
                  {message.sources.length}
                </Button>
              </Tooltip>
            )}
          </div>
        )}

        {isComplete && message.highlightDocuments && message.highlightDocuments.length > 0 && (
          <>
            <div
              role="group"
              aria-label="Hồ sơ đã highlight"
              style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}
            >
              {message.highlightDocuments.map((doc) => (
                <button
                  key={doc.url}
                  type="button"
                  onClick={() => onOpenHighlightDocument?.(doc)}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    padding: 0,
                    cursor: 'pointer',
                    width: 148,
                  }}
                  aria-label={`Mở ${doc.name} ở panel hồ sơ`}
                >
                  <Image
                    src={doc.url}
                    alt={doc.name}
                    width={148}
                    height={104}
                    preview={false}
                    style={{
                      objectFit: 'cover',
                      borderRadius: 10,
                      border: '1px solid #EAE3DA',
                    }}
                  />
                  <span
                    style={{
                      display: 'block',
                      fontSize: 12,
                      color: '#667085',
                      marginTop: 4,
                      textAlign: 'center',
                    }}
                  >
                    {doc.name}
                  </span>
                </button>
              ))}
            </div>

            {/* Dẫn chứng kiểu NotebookLM: mỗi vùng trích một chip đánh số,
                bấm mở viewer panel phải và khoanh đỏ đúng dòng trên hồ sơ gốc. */}
            {(() => {
              const citations = (message.highlightDocuments ?? []).flatMap((doc) =>
                (doc.regions ?? []).map((region) => ({ doc, region })),
              );
              if (citations.length === 0) return null;
              return (
                <div style={{ marginTop: 10 }} role="list" aria-label="Dẫn chứng trên hồ sơ">
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#2F2E79' }}>
                    📎 Dẫn chứng trên hồ sơ gốc:
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                    {citations.map(({ doc, region }, index) => (
                      <button
                        key={`${doc.url}-${region.id}`}
                        type="button"
                        role="listitem"
                        onClick={() =>
                          onOpenHighlightDocument?.({ ...doc, activeRegionId: region.id })
                        }
                        style={{
                          display: 'flex',
                          alignItems: 'baseline',
                          gap: 8,
                          textAlign: 'left',
                          border: '1px solid #EAE3DA',
                          background: '#FFFDF9',
                          borderRadius: 8,
                          padding: '6px 10px',
                          cursor: 'pointer',
                        }}
                        title={region.label}
                        aria-label={`Dẫn chứng ${index + 1}: ${region.quote}`}
                      >
                        <span
                          aria-hidden="true"
                          style={{
                            flexShrink: 0,
                            width: 18,
                            height: 18,
                            borderRadius: 9,
                            background: '#F37021',
                            color: '#fff',
                            fontSize: 11,
                            fontWeight: 700,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {index + 1}
                        </span>
                        <span style={{ fontSize: 13, color: '#18212B', minWidth: 0 }}>
                          <span style={{ fontStyle: 'italic' }}>“{region.quote}”</span>
                          {region.label && (
                            <span style={{ display: 'block', fontSize: 12, color: '#667085' }}>
                              {region.label}
                            </span>
                          )}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })()}
          </>
        )}

        {isComplete && message.suggestions && message.suggestions.length > 0 && (
          <SuggestedQuestions suggestions={message.suggestions} onSelect={onPrompt} disabled={busy} />
        )}
      </div>
    </motion.div>
  );
}
