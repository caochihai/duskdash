import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteConversation } from '@/services/conversationService';
import type { Conversation } from '@/types/conversation';
import { chatQueryKeys } from './queryKeys';

/**
 * Xoá hội thoại với optimistic update + rollback khi lỗi.
 */
export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (conversationId: string) => deleteConversation(conversationId),

    onMutate: async (conversationId) => {
      await queryClient.cancelQueries({ queryKey: chatQueryKeys.conversations() });

      const previous = queryClient.getQueryData<Conversation[]>(chatQueryKeys.conversations());

      queryClient.setQueryData<Conversation[]>(chatQueryKeys.conversations(), (current) =>
        current?.filter((item) => item.id !== conversationId),
      );

      return { previous };
    },

    onError: (_error, _conversationId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(chatQueryKeys.conversations(), context.previous);
      }
    },

    onSuccess: (_data, conversationId) => {
      queryClient.removeQueries({ queryKey: chatQueryKeys.messages(conversationId) });
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: chatQueryKeys.conversations() });
    },
  });
}
