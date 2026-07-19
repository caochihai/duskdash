import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { appendUserMessage, streamAssistantResponse } from '@/services/chatService';
import { getErrorMessage, USE_MOCK_API } from '@/services/apiClient';
import { chatQueryKeys } from './queryKeys';
import type { AIProcessingPhase, ChatMessage, ChatMode } from '@/types/chat';
import type { ChatAttachment } from '@/types/attachment';

export interface SendMessageInput {
  conversationId?: string;
  content: string;
  attachments?: ChatAttachment[];
  mode?: ChatMode;
  assignmentLeaseToken?: string;
  /** Khách hàng mà phiên chat đang gắn vào (nếu là phiên của một khách hàng). */
  customerId?: string;
}

interface UseSendMessageResult {
  /** Tin nhắn AI đang được tạo — chưa nằm trong query cache. */
  streamingMessage: ChatMessage | null;
  /** Phase xử lý cấp cao hiện tại. */
  phase: AIProcessingPhase | null;
  isStreaming: boolean;
  send: (input: SendMessageInput) => Promise<void>;
  stop: () => void;
  /** Gửi lại câu hỏi gần nhất (dùng cho "Tạo lại câu trả lời"). */
  regenerate: () => Promise<void>;
  canRegenerate: boolean;
}

function createId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Điều phối luồng gửi tin nhắn và nhận câu trả lời streaming.
 *
 * Đây là server-state có vòng đời đặc biệt (stream dài, có thể huỷ), nên tin nhắn
 * đang stream được giữ ở local state và chỉ ghi vào TanStack Query cache khi
 * hoàn tất/dừng/lỗi. Nhờ vậy cache không bị ghi lại sau mỗi ký tự.
 */
export function useSendMessage(conversationId: string | null): UseSendMessageResult {
  const queryClient = useQueryClient();

  const [streamingMessage, setStreamingMessage] = useState<ChatMessage | null>(null);
  const [phase, setPhase] = useState<AIProcessingPhase | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const lastInputRef = useRef<SendMessageInput | null>(null);
  /** Giữ bản mới nhất của message đang stream để `stop()` đọc được ngay. */
  const streamingRef = useRef<ChatMessage | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      // Huỷ stream khi unmount -> không setState sau unmount, không rò rỉ timer.
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const updateStreaming = useCallback((message: ChatMessage | null) => {
    streamingRef.current = message;
    if (mountedRef.current) setStreamingMessage(message);
  }, []);

  /** Đưa một message vào query cache của hội thoại. */
  const commitToCache = useCallback(
    (message: ChatMessage) => {
      queryClient.setQueryData<ChatMessage[]>(
        chatQueryKeys.messages(message.conversationId),
        (current) => {
          const list = current ?? [];
          const index = list.findIndex((item) => item.id === message.id);
          if (index === -1) return [...list, message];
          const next = [...list];
          next[index] = message;
          return next;
        },
      );
    },
    [queryClient],
  );

  const runStream = useCallback(
    async (input: SendMessageInput, targetConversationId: string) => {
      const controller = new AbortController();
      abortRef.current = controller;

      const assistantId = createId('msg-assistant');
      const assistantBase: ChatMessage = {
        id: assistantId,
        conversationId: targetConversationId,
        role: 'assistant',
        content: '',
        status: 'thinking',
        createdAt: new Date().toISOString(),
        phase: 'connecting',
      };

      updateStreaming(assistantBase);
      if (mountedRef.current) setPhase('connecting');

      try {
        const stream = streamAssistantResponse(targetConversationId, input.content, {
          mode: input.mode,
          hasAttachment: Boolean(input.attachments?.length),
          signal: controller.signal,
          ...(input.customerId ? { customerId: input.customerId } : {}),
        });

        for await (const event of stream) {
          if (!mountedRef.current || controller.signal.aborted) break;

          switch (event.type) {
            case 'phase': {
              setPhase(event.phase);
              const current = streamingRef.current;
              if (current) {
                updateStreaming({ ...current, phase: event.phase, status: 'thinking' });
              }
              break;
            }

            case 'delta': {
              const current = streamingRef.current;
              if (current) {
                updateStreaming({
                  ...current,
                  content: current.content + event.text,
                  status: 'streaming',
                });
              }
              break;
            }

            case 'complete': {
              commitToCache(event.message);
              updateStreaming(null);
              if (mountedRef.current) setPhase(null);
              // Sidebar cần cập nhật thứ tự + preview.
              void queryClient.invalidateQueries({ queryKey: chatQueryKeys.conversations() });
              break;
            }

            case 'error': {
              const current = streamingRef.current;
              if (current) {
                const errored: ChatMessage = {
                  ...current,
                  status: 'error',
                  errorMessage: event.error.message,
                };
                commitToCache(errored);
              }
              updateStreaming(null);
              if (mountedRef.current) setPhase(null);
              break;
            }
          }
        }
      } catch (error) {
        // AbortError là hành vi chủ đích (người dùng bấm dừng / unmount).
        if (error instanceof DOMException && error.name === 'AbortError') return;

        const current = streamingRef.current;
        if (current) {
          commitToCache({
            ...current,
            status: 'error',
            errorMessage: getErrorMessage(error),
          });
        }
        updateStreaming(null);
        if (mountedRef.current) setPhase(null);
      } finally {
        abortRef.current = null;
      }
    },
    [commitToCache, queryClient, updateStreaming],
  );

  const send = useCallback(
    async (input: SendMessageInput) => {
      const targetConversationId = input.conversationId ?? conversationId;
      if (!targetConversationId) return;
      // Chặn gửi trùng khi đang stream (double click / Enter nhiều lần).
      if (abortRef.current) return;

      lastInputRef.current = input;

      // 1. Optimistic: tin nhắn người dùng hiện ra ngay lập tức.
      const optimisticUser: ChatMessage = {
        id: createId('msg-user'),
        conversationId: targetConversationId,
        role: 'user',
        content: input.content,
        status: 'completed',
        createdAt: new Date().toISOString(),
        ...(input.attachments?.length ? { attachments: input.attachments } : {}),
      };
      commitToCache(optimisticUser);

      if (!USE_MOCK_API) {
        abortRef.current = new AbortController();
        updateStreaming({
          id: createId('msg-assistant'),
          conversationId: targetConversationId,
          role: 'assistant',
          content: '',
          status: 'thinking',
          createdAt: new Date().toISOString(),
          phase: 'connecting',
        });
        if (mountedRef.current) setPhase('connecting');
      }

      // 2. Ghi nhận ở phía service (mock hoặc backend).
      try {
        const result = await appendUserMessage(
          targetConversationId,
          input.content,
          input.attachments ?? [],
          input.mode ?? 'general',
          input.assignmentLeaseToken,
        );

        queryClient.setQueryData<ChatMessage[]>(
          chatQueryKeys.messages(targetConversationId),
          (current) => (current ?? []).filter((item) => item.id !== optimisticUser.id),
        );
        commitToCache(result.userMessage);

        if (result.assistantMessage) {
          commitToCache(result.assistantMessage);
          updateStreaming(null);
          if (mountedRef.current) setPhase(null);
          void queryClient.invalidateQueries({ queryKey: chatQueryKeys.conversations() });
          return;
        }
      } catch (error) {
        commitToCache({
          ...optimisticUser,
          status: 'error',
          errorMessage: getErrorMessage(error),
        });
        updateStreaming(null);
        if (mountedRef.current) setPhase(null);
        return;
      } finally {
        if (!USE_MOCK_API) abortRef.current = null;
      }

      // 3. Nhận câu trả lời AI.
      await runStream(input, targetConversationId);
    },
    [conversationId, commitToCache, queryClient, runStream, updateStreaming],
  );

  const stop = useCallback(() => {
    const current = streamingRef.current;
    abortRef.current?.abort();
    abortRef.current = null;

    /*
     * Luôn ghi lại tin nhắn ở trạng thái 'stopped', kể cả khi chưa stream được
     * ký tự nào (người dùng bấm dừng ngay lúc AI còn đang xử lý).
     * Nếu bỏ qua, tin nhắn sẽ biến mất im lặng và người dùng không biết
     * thao tác dừng đã có tác dụng hay chưa.
     */
    if (current) {
      commitToCache({ ...current, status: 'stopped' });
    }

    updateStreaming(null);
    if (mountedRef.current) setPhase(null);
  }, [commitToCache, updateStreaming]);

  const regenerate = useCallback(async () => {
    if (!conversationId || !lastInputRef.current || abortRef.current) return;
    if (USE_MOCK_API) {
      await runStream(lastInputRef.current, conversationId);
      return;
    }
    await send({ ...lastInputRef.current, conversationId });
  }, [conversationId, runStream, send]);

  return {
    streamingMessage,
    phase,
    isStreaming: streamingMessage !== null,
    send,
    stop,
    regenerate,
    canRegenerate: lastInputRef.current !== null,
  };
}
