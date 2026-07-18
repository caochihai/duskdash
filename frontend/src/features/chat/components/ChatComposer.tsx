import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Sender } from '@ant-design/x';
import { App, Button, Tooltip, Upload } from 'antd';
import { PaperClipOutlined } from '@ant-design/icons';
import { AttachmentPreview } from './AttachmentPreview';
import { AIDisclaimer } from './AIDisclaimer';
import { SecurityAlert } from './SecurityAlert';
import { SlashCommandPopup } from './SlashCommandPopup';
import { AnimatePresence } from 'motion/react';
import { normalizeVietnamese } from '@/utils/detectSensitiveContent';
import type { Customer } from '@/types/customer';
import { uploadAttachment, validateAttachment } from '@/services/attachmentService';
import { getErrorMessage } from '@/services/apiClient';
import { detectSensitiveContent, type SensitiveDetection } from '@/utils/detectSensitiveContent';
import { ACCEPTED_FILE_EXTENSIONS, ATTACHMENT_LIMITS, type ChatAttachment } from '@/types/attachment';
import styles from './ChatComposer.module.css';

export interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (content: string, attachments: ChatAttachment[]) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  placeholder?: string;
  /** Danh sách khách hàng cho lệnh `/`. */
  customers?: Customer[];
  /** Gọi khi chuyên viên chọn một khách hàng từ popup `/`. */
  onSelectCustomer?: (customer: Customer) => void;
  /** Gọi khi upload hồ sơ chưa gắn khách hàng và backend đã tự tạo khách nháp. */
  onCustomerAutoCreated?: (customerId: string) => void;
  uploadContext?: { customerId?: string; loanApplicationId?: string };
}

function createId(): string {
  return `att-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Composer — thành phần tương tác quan trọng nhất.
 *
 * Dựng trên Ant Design X `Sender`:
 * - Enter gửi, Shift + Enter xuống dòng (mặc định của Sender).
 * - Khi AI đang trả lời, nút gửi tự đổi thành nút dừng qua `loading` + `onCancel`.
 *
 * Attachment là state cục bộ của composer cho tới khi tin nhắn được gửi đi.
 */
export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming,
  disabled = false,
  placeholder = 'Hỏi SH-AI, hoặc gõ / để tra cứu khách hàng...',
  customers = [],
  onSelectCustomer,
  onCustomerAutoCreated,
  uploadContext,
}: ChatComposerProps) {
  const { message: messageApi } = App.useApp();

  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [detection, setDetection] = useState<SensitiveDetection | null>(null);
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [slashIndex, setSlashIndex] = useState(0);

  // Huỷ mọi upload đang chạy khi composer unmount.
  const uploadControllersRef = useRef(new Map<string, AbortController>());

  useEffect(() => {
    const controllers = uploadControllersRef.current;
    return () => {
      controllers.forEach((controller) => controller.abort());
      controllers.clear();
    };
  }, []);

  // Cảnh báo bảo mật theo nội dung đang gõ.
  useEffect(() => {
    const result = detectSensitiveContent(value);
    setDetection(result);
    if (!result) setAlertDismissed(false);
  }, [value]);

  const updateAttachment = useCallback((id: string, patch: Partial<ChatAttachment>) => {
    setAttachments((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  }, []);

  const runUpload = useCallback(
    async (id: string, file: File) => {
      const controller = new AbortController();
      uploadControllersRef.current.set(id, controller);

      try {
        const uploaded = await uploadAttachment(file, {
          signal: controller.signal,
          onProgress: (percent) => updateAttachment(id, { progress: percent }),
          customerId: uploadContext?.customerId,
          loanApplicationId: uploadContext?.loanApplicationId,
        });
        // Giữ nguyên id cục bộ để tránh nhảy key trong danh sách.
        updateAttachment(id, { ...uploaded, id });
        // Upload khi chưa chọn khách hàng -> backend đã tự tạo khách nháp;
        // báo lên trên để gắn khách hàng đó vào phiên chat.
        if (!uploadContext?.customerId && uploaded.customerId) {
          onCustomerAutoCreated?.(uploaded.customerId);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        updateAttachment(id, { status: 'error', errorMessage: getErrorMessage(error) });
      } finally {
        uploadControllersRef.current.delete(id);
      }
    },
    [updateAttachment, uploadContext, onCustomerAutoCreated],
  );

  const handleAddFile = useCallback(
    (file: File): boolean => {
      if (attachments.length >= ATTACHMENT_LIMITS.maxFiles) {
        messageApi.warning(`Chỉ đính kèm tối đa ${ATTACHMENT_LIMITS.maxFiles} tài liệu.`);
        return false;
      }

      const validationError = validateAttachment(
        file,
        attachments.map((item) => item.name),
      );

      const id = createId();

      if (validationError) {
        // Vẫn hiển thị file lỗi để người dùng hiểu vì sao bị từ chối.
        setAttachments((current) => [
          ...current,
          {
            id,
            name: file.name,
            mimeType: file.type,
            size: file.size,
            status: 'error',
            errorMessage: validationError,
          },
        ]);
        return false;
      }

      setAttachments((current) => [
        ...current,
        {
          id,
          name: file.name,
          mimeType: file.type,
          size: file.size,
          status: 'uploading',
          progress: 0,
        },
      ]);

      void runUpload(id, file);
      return false; // Upload thủ công -> chặn hành vi mặc định của antd Upload.
    },
    [attachments, messageApi, runUpload],
  );

  const handleRemove = useCallback((id: string) => {
    uploadControllersRef.current.get(id)?.abort();
    uploadControllersRef.current.delete(id);
    setAttachments((current) => current.filter((item) => item.id !== id));
  }, []);

  /* ---------------- Lệnh `/` tra cứu khách hàng ---------------- */

  /**
   * Popup mở khi nội dung bắt đầu bằng `/`. Phần sau dấu `/` là từ khoá lọc,
   * so khớp không dấu để gõ "nhung" tìm được "Trần Thị Hồng Nhung".
   */
  const slashQuery = value.startsWith('/') ? value.slice(1) : null;

  const slashMatches = useMemo(() => {
    if (slashQuery === null) return [];
    const term = normalizeVietnamese(slashQuery);
    if (!term) return customers;

    return customers.filter((customer) =>
      normalizeVietnamese(`${customer.fullName} ${customer.code} ${customer.branch}`).includes(term),
    );
  }, [customers, slashQuery]);

  const slashOpen = slashQuery !== null && Boolean(onSelectCustomer) && customers.length > 0;

  // Đổi từ khoá -> đưa lựa chọn về đầu danh sách.
  useEffect(() => {
    setSlashIndex(0);
  }, [slashQuery]);

  const handleSelectCustomer = useCallback(
    (customer: Customer) => {
      onSelectCustomer?.(customer);
      onChange('');
    },
    [onChange, onSelectCustomer],
  );

  const readyAttachments = useMemo(
    () => attachments.filter((item) => item.status === 'done'),
    [attachments],
  );

  const hasPendingUpload = attachments.some((item) => item.status === 'uploading');

  const canSend =
    !disabled &&
    !hasPendingUpload &&
    // Đang ở chế độ lệnh `/` -> Enter dùng để chọn khách hàng, không phải gửi.
    !slashOpen &&
    (value.trim().length > 0 || readyAttachments.length > 0);

  const handleSubmit = useCallback(() => {
    if (!canSend || isStreaming) return;

    onSend(value.trim(), readyAttachments);
    setAttachments([]);
    setDetection(null);
    setAlertDismissed(false);
  }, [canSend, isStreaming, onSend, readyAttachments, value]);

  return (
    <div className={styles.wrapper}>
      <div className={styles.inner}>
        <SecurityAlert
          detection={alertDismissed ? null : detection}
          onClose={() => setAlertDismissed(true)}
        />

        <div className={styles.shellAnchor}>
          <AnimatePresence>
            {slashOpen && (
              <SlashCommandPopup
                customers={slashMatches}
                activeIndex={slashIndex}
                onHover={setSlashIndex}
                onSelect={handleSelectCustomer}
              />
            )}
          </AnimatePresence>

          <div className={styles.composerShell}>
          <Sender
            className={styles.sender}
            value={value}
            onChange={(next) => onChange(next)}
            onSubmit={handleSubmit}
            onCancel={onStop}
            loading={isStreaming}
            disabled={disabled}
            placeholder={placeholder}
            autoSize={{ minRows: 1, maxRows: 8 }}
            /*
             * Trả về `false` để huỷ hành vi Enter-gửi mặc định của Sender khi
             * popup `/` đang mở (Enter lúc này dùng để chọn khách hàng).
             */
            onKeyDown={(event) => {
              if (slashOpen) {
                if (event.key === 'ArrowDown') {
                  event.preventDefault();
                  setSlashIndex((index) => (index + 1) % Math.max(slashMatches.length, 1));
                  return false;
                }
                if (event.key === 'ArrowUp') {
                  event.preventDefault();
                  setSlashIndex(
                    (index) =>
                      (index - 1 + Math.max(slashMatches.length, 1)) %
                      Math.max(slashMatches.length, 1),
                  );
                  return false;
                }
                if (event.key === 'Enter') {
                  const picked = slashMatches[slashIndex];
                  if (picked) {
                    event.preventDefault();
                    handleSelectCustomer(picked);
                  }
                  return false;
                }
                if (event.key === 'Escape') {
                  event.preventDefault();
                  onChange('');
                  return false;
                }
              }

              // Esc: đóng cảnh báo bảo mật (trạng thái phụ) thay vì xoá nội dung đang gõ.
              if (event.key === 'Escape' && detection && !alertDismissed) {
                setAlertDismissed(true);
              }
              return undefined;
            }}
            onPasteFile={(files) => {
              Array.from(files).forEach((file) => handleAddFile(file));
            }}
            header={
              attachments.length > 0 ? (
                <Sender.Header open forceRender styles={{ content: { padding: 0 } }}>
                  <AttachmentPreview attachments={attachments} onRemove={handleRemove} />
                </Sender.Header>
              ) : undefined
            }
            prefix={
              <Upload
                accept={ACCEPTED_FILE_EXTENSIONS}
                multiple
                showUploadList={false}
                beforeUpload={handleAddFile}
                disabled={disabled || attachments.length >= ATTACHMENT_LIMITS.maxFiles}
              >
                <Tooltip title="Đính kèm tài liệu">
                  <Button
                    type="text"
                    shape="circle"
                    icon={<PaperClipOutlined />}
                    aria-label="Đính kèm tài liệu"
                    disabled={disabled || attachments.length >= ATTACHMENT_LIMITS.maxFiles}
                  />
                </Tooltip>
              </Upload>
            }
            suffix={(_oriNode, { components }) => {
              const { SendButton, LoadingButton } = components;

              // Đang trả lời -> nút dừng (LoadingButton gọi onCancel).
              if (isStreaming) {
                return (
                  <Tooltip title="Dừng tạo câu trả lời">
                    <LoadingButton aria-label="Dừng tạo câu trả lời" />
                  </Tooltip>
                );
              }

              /*
               * Truyền `disabled` tường minh để ghi đè logic mặc định của Sender:
               * cho phép gửi khi chỉ có tài liệu đính kèm mà chưa nhập chữ.
               */
              return (
                <Tooltip title={canSend ? 'Gửi' : 'Nhập nội dung để gửi'}>
                  <SendButton disabled={!canSend} aria-label="Gửi" />
                </Tooltip>
              );
            }}
            />
          </div>
        </div>

        <AIDisclaimer />
      </div>
    </div>
  );
}
