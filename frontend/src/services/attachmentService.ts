import apiClient, { USE_MOCK_API } from './apiClient';
import { mockUploadAttachment, validateAttachment } from './mockApi';
import type { ChatAttachment } from '@/types/attachment';
import type { BackendUploadComplete, BackendUploadSession } from '@/types/backend';

export interface UploadOptions {
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
  customerId?: string;
  loanApplicationId?: string;
}

/** Upload một tài liệu đính kèm. */
export async function uploadAttachment(
  file: File,
  options: UploadOptions = {},
): Promise<ChatAttachment> {
  if (USE_MOCK_API) return mockUploadAttachment(file, options);

  if (!options.customerId) {
    throw new Error('Vui lòng chọn khách hàng trước khi tải tài liệu.');
  }

  options.onProgress?.(5);
  const expectedSha256 = await sha256Hex(file);
  const upload = await apiClient.post<BackendUploadSession>(
    '/documents/uploads',
    {
      customer_id: options.customerId,
      loan_application_id: options.loanApplicationId,
      original_filename: file.name,
      expected_mime_type: file.type || 'application/octet-stream',
      expected_size_bytes: file.size,
      expected_sha256: expectedSha256,
    },
    {
      headers: { 'Idempotency-Key': crypto.randomUUID() },
      signal: options.signal,
    },
  );

  options.onProgress?.(25);
  const objectUpload = await fetch(upload.data.upload_url, {
    method: 'PUT',
    headers: upload.data.headers,
    body: file,
    signal: options.signal,
  });
  if (!objectUpload.ok) {
    throw new Error('Không thể tải nội dung tài liệu lên kho lưu trữ.');
  }

  options.onProgress?.(85);
  const completed = await apiClient.post<BackendUploadComplete>(
    `/documents/uploads/${upload.data.upload_id}/complete`,
    {},
    {
      headers: { 'Idempotency-Key': crypto.randomUUID() },
      signal: options.signal,
    },
  );
  options.onProgress?.(100);
  return {
    id: completed.data.document_id,
    name: file.name,
    mimeType: file.type,
    size: file.size,
    status: 'done',
    progress: 100,
  };
}

async function sha256Hex(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export { validateAttachment };
