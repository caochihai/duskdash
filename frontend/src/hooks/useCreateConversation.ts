import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createConversation,
  type CreateConversationInput,
} from '@/services/conversationService';
import type { Conversation } from '@/types/conversation';
import { chatQueryKeys } from './queryKeys';

/** Tạo hội thoại mới, đưa ngay vào cache để sidebar cập nhật tức thì. */
export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateConversationInput = {}) => createConversation(input),
    onSuccess: (conversation) => {
      queryClient.setQueryData<Conversation[]>(chatQueryKeys.conversations(), (previous) =>
        previous ? [conversation, ...previous] : [conversation],
      );
      // Hội thoại mới chưa có tin nhắn -> seed cache rỗng, tránh loading thừa.
      queryClient.setQueryData(chatQueryKeys.messages(conversation.id), []);
    },
  });
}
