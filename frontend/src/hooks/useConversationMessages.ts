import { useQuery } from '@tanstack/react-query';
import { getMessages } from '@/services/chatService';
import { chatQueryKeys } from './queryKeys';

/** Tin nhắn của một hội thoại. Bỏ qua fetch khi chưa chọn hội thoại nào. */
export function useConversationMessages(conversationId: string | null) {
  return useQuery({
    queryKey: chatQueryKeys.messages(conversationId ?? ''),
    queryFn: ({ signal }) => getMessages(conversationId as string, signal),
    enabled: Boolean(conversationId),
    staleTime: 15_000,
  });
}
