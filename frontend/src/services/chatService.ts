import apiClient, { USE_MOCK_API } from './apiClient';
import { mockAppendUserMessage, mockGetMessages, mockStreamAssistantResponse } from './mockApi';
import type { ChatAttachment } from '@/types/attachment';
import type { ChatMessage, ChatMode } from '@/types/chat';
import type { GetMessagesResponse, SendMessageResponse, StreamEvent } from '@/types/api';

/** Lấy toàn bộ tin nhắn của một hội thoại. */
export async function getMessages(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ChatMessage[]> {
  if (USE_MOCK_API) return mockGetMessages(conversationId, signal);

  const response = await apiClient.get<GetMessagesResponse>(
    `/conversations/${conversationId}/messages`,
    { signal },
  );
  return response.data.data;
}

/** Ghi nhận tin nhắn của người dùng. */
export async function appendUserMessage(
  conversationId: string,
  content: string,
  attachments: ChatAttachment[] = [],
  mode: ChatMode = 'general',
): Promise<ChatMessage> {
  if (USE_MOCK_API) return mockAppendUserMessage(conversationId, content, attachments);

  const response = await apiClient.post<SendMessageResponse>(
    `/conversations/${conversationId}/messages`,
    {
      content,
      attachmentIds: attachments.map((item) => item.id),
      mode,
    },
  );
  return response.data.message;
}

export interface StreamOptions {
  mode?: ChatMode;
  hasAttachment?: boolean;
  signal?: AbortSignal;
}

/**
 * Nhận câu trả lời của AI theo dạng stream.
 *
 * Ở chế độ mock: async generator mô phỏng.
 * Ở chế độ thật: backend có thể trả SSE / WebSocket / chunked HTTP — chỉ cần
 * phát ra cùng hình dạng `StreamEvent`, phần UI không phải thay đổi.
 */
export async function* streamAssistantResponse(
  conversationId: string,
  content: string,
  options: StreamOptions = {},
): AsyncGenerator<StreamEvent> {
  if (USE_MOCK_API) {
    yield* mockStreamAssistantResponse(conversationId, content, options);
    return;
  }

  // Backend thật: đọc chunked response và phát lại thành StreamEvent.
  const baseUrl = import.meta.env.VITE_API_BASE_URL;
  const response = await fetch(`${baseUrl}/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, mode: options.mode }),
    signal: options.signal,
  });

  if (!response.ok || !response.body) {
    throw new Error('Stream request failed');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Mỗi sự kiện là một dòng JSON (NDJSON).
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        yield JSON.parse(trimmed) as StreamEvent;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
