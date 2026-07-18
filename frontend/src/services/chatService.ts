import apiClient, { USE_MOCK_API } from './apiClient';
import { mockAppendUserMessage, mockGetMessages, mockStreamAssistantResponse } from './mockApi';
import { toChatMessage } from './backendAdapters';
import type { ChatAttachment } from '@/types/attachment';
import type { ChatMessage, ChatMode } from '@/types/chat';
import type { StreamEvent } from '@/types/api';
import type { BackendConversationTurn, BackendMessage } from '@/types/backend';

export async function getMessages(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ChatMessage[]> {
  if (USE_MOCK_API) return mockGetMessages(conversationId, signal);

  const response = await apiClient.get<BackendMessage[]>(
    `/conversations/${conversationId}/messages`,
    { signal },
  );
  return response.data.map((item) => toChatMessage(item));
}

export interface ConversationTurnResult {
  userMessage: ChatMessage;
  assistantMessage?: ChatMessage;
}

/** Persist one employee message and return the synchronous assistant turn when available. */
export async function appendUserMessage(
  conversationId: string,
  content: string,
  attachments: ChatAttachment[] = [],
  mode: ChatMode = 'general',
  assignmentLeaseToken?: string,
): Promise<ConversationTurnResult> {
  if (USE_MOCK_API) {
    return {
      userMessage: await mockAppendUserMessage(conversationId, content, attachments),
    };
  }

  const response = await apiClient.post<BackendConversationTurn>(
    `/conversations/${conversationId}/messages`,
    {
      content,
      attachment_ids: attachments.map((item) => item.id),
    },
    {
      // Phân tích sâu (vision đọc hồ sơ / hội đồng multi-agent) chạy đồng bộ
      // 20–90 giây — timeout mặc định 30s sẽ huỷ request giữa chừng khiến
      // câu trả lời "biến mất" dù server vẫn xử lý xong.
      timeout: 180_000,
      headers: assignmentLeaseToken
        ? { 'X-Customer-Assignment-Lease-Token': assignmentLeaseToken }
        : undefined,
    },
  );
  const userMessage: ChatMessage = {
    ...toChatMessage(response.data),
    ...(attachments.length ? { attachments } : {}),
  };
  const assistantMessage = response.data.assistant_message
    ? toChatMessage(response.data.assistant_message, response.data.reply)
    : undefined;

  // The backend router determines the agent route from content and resource context.
  void mode;
  return {
    userMessage,
    ...(assistantMessage ? { assistantMessage } : {}),
  };
}

export interface StreamOptions {
  mode?: ChatMode;
  hasAttachment?: boolean;
  signal?: AbortSignal;
}

/** The existing animated stream remains available for the isolated frontend mock. */
export async function* streamAssistantResponse(
  conversationId: string,
  content: string,
  options: StreamOptions = {},
): AsyncGenerator<StreamEvent> {
  if (USE_MOCK_API) {
    yield* mockStreamAssistantResponse(conversationId, content, options);
    return;
  }

  throw new Error(
    `Conversation ${conversationId} uses the synchronous backend turn API; no stream was opened.`,
  );
}
