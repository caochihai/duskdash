export type AttachmentStatus = 'pending' | 'uploading' | 'done' | 'error' | 'removed';

export interface ChatAttachment {
  id: string;
  name: string;
  mimeType: string;
  /** Bytes. */
  size: number;
  status: AttachmentStatus;
  /** 0–100, chỉ có ý nghĩa khi status = 'uploading'. */
  progress?: number;
  errorMessage?: string;
  /** Khách hàng gắn với hồ sơ (backend tự tạo khách nháp khi chưa chọn). */
  customerId?: string;
}

/** Giới hạn demo cho attachment. */
export const ATTACHMENT_LIMITS = {
  maxSizeBytes: 10 * 1024 * 1024, // 10 MB
  maxNameLength: 120,
  maxFiles: 5,
} as const;

/** Định dạng được chấp nhận ở chế độ demo. */
export const ACCEPTED_MIME_TYPES: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/msword': 'DOC',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
  'application/vnd.ms-excel': 'XLS',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
  'image/png': 'PNG',
  'image/jpeg': 'JPG',
};

export const ACCEPTED_FILE_EXTENSIONS = '.pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg';
