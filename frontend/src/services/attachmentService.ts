import apiClient, { USE_MOCK_API } from './apiClient';
import { mockUploadAttachment, validateAttachment } from './mockApi';
import type { ChatAttachment } from '@/types/attachment';
import type { UploadAttachmentResponse } from '@/types/api';

export interface UploadOptions {
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

/** Upload một tài liệu đính kèm. */
export async function uploadAttachment(
  file: File,
  options: UploadOptions = {},
): Promise<ChatAttachment> {
  if (USE_MOCK_API) return mockUploadAttachment(file, options);

  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadAttachmentResponse>('/attachments', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    signal: options.signal,
    onUploadProgress: (event) => {
      if (event.total) {
        options.onProgress?.(Math.round((event.loaded / event.total) * 100));
      }
    },
  });

  return response.data.attachment;
}

export { validateAttachment };
