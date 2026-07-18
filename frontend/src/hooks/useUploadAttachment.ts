import { useMutation } from '@tanstack/react-query';
import { uploadAttachment } from '@/services/attachmentService';
import type { ChatAttachment } from '@/types/attachment';

interface UploadVariables {
  file: File;
  onProgress?: (percent: number) => void;
}

/**
 * Upload tài liệu đính kèm.
 *
 * Không invalidate query nào: attachment thuộc về state cục bộ của composer
 * cho tới khi tin nhắn được gửi đi.
 */
export function useUploadAttachment() {
  return useMutation<ChatAttachment, unknown, UploadVariables>({
    mutationFn: ({ file, onProgress }) => uploadAttachment(file, { onProgress }),
  });
}
