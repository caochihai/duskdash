import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateConversation } from '@/services/conversationService';
import type { Conversation } from '@/types/conversation';
import { chatQueryKeys } from './queryKeys';

interface RenameVariables {
  conversationId: string;
  title: string;
}

/**
 * Đổi tên hội thoại với optimistic update.
 * Nếu mutation lỗi, cache được rollback về trạng thái trước đó.
 */
export function useRenameConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ conversationId, title }: RenameVariables) =>
      updateConversation(conversationId, { title }),

    onMutate: async ({ conversationId, title }) => {
      await queryClient.cancelQueries({ queryKey: chatQueryKeys.conversations() });

      const previous = queryClient.getQueryData<Conversation[]>(chatQueryKeys.conversations());

      queryClient.setQueryData<Conversation[]>(chatQueryKeys.conversations(), (current) =>
        current?.map((item) => (item.id === conversationId ? { ...item, title } : item)),
      );

      return { previous };
    },

    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(chatQueryKeys.conversations(), context.previous);
      }
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: chatQueryKeys.conversations() });
    },
  });
}
