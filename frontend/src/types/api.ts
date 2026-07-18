import type { ChatMessage, ChatMode } from './chat';
import type { Conversation } from './conversation';
import type { ChatAttachment } from './attachment';

/** Lỗi API đã được chuẩn hoá bởi `apiClient` interceptor. */
export interface ApiError {
  code: string;
  message: string;
  status?: number;
  details?: unknown;
}

/** Mã lỗi nội bộ, dùng để chọn thông điệp tiếng Việt phù hợp. */
export const API_ERROR_CODES = {
  timeout: 'ERR_TIMEOUT',
  network: 'ERR_NETWORK',
  notFound: 'ERR_NOT_FOUND',
  unauthorized: 'ERR_UNAUTHORIZED',
  server: 'ERR_SERVER',
  unknown: 'ERR_UNKNOWN',
  uploadFailed: 'ERR_UPLOAD_FAILED',
  validation: 'ERR_VALIDATION',
} as const;

export type ApiErrorCode = (typeof API_ERROR_CODES)[keyof typeof API_ERROR_CODES];

/* ---------------- Conversations ---------------- */

export interface GetConversationsResponse {
  data: Conversation[];
}

export interface GetConversationResponse {
  data: Conversation;
}

export interface CreateConversationRequest {
  title?: string;
}

export interface CreateConversationResponse {
  data: Conversation;
}

export interface UpdateConversationRequest {
  title?: string;
  pinned?: boolean;
}

export interface UpdateConversationResponse {
  data: Conversation;
}

/* ---------------- Messages ---------------- */

export interface GetMessagesResponse {
  data: ChatMessage[];
}

export interface SendMessageRequest {
  content: string;
  attachmentIds?: string[];
  mode?: ChatMode;
}

export interface SendMessageResponse {
  message: ChatMessage;
}

/* ---------------- Attachments ---------------- */

export interface UploadAttachmentResponse {
  attachment: ChatAttachment;
}

/* ---------------- Streaming ---------------- */

/**
 * Sự kiện streaming từ backend.
 * Frontend demo dùng async generator mock; backend thật có thể dùng
 * SSE / WebSocket / chunked HTTP với cùng hình dạng sự kiện này.
 */
export type StreamEvent =
  | { type: 'phase'; phase: import('./chat').AIProcessingPhase }
  | { type: 'delta'; text: string }
  | { type: 'complete'; message: ChatMessage }
  | { type: 'error'; error: ApiError };
