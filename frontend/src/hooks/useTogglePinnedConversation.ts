import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateConversation } from '@/services/conversationService';
import type { Conversation } from '@/types/conversation';
import { chatQueryKeys } from './queryKeys';

interface TogglePinVariables {
  conversationId: string;
  pinned: boolean;
}

/** Ghim / bỏ ghim hội thoại với optimistic update. */
export function useTogglePinnedConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ conversationId, pinned }: TogglePinVariables) =>
      updateConversation(conversationId, { pinned }),

    onMutate: async ({ conversationId, pinned }) => {
      await queryClient.cancelQueries({ queryKey: chatQueryKeys.conversations() });

      const previous = queryClient.getQueryData<Conversation[]>(chatQueryKeys.conversations());

      queryClient.setQueryData<Conversation[]>(chatQueryKeys.conversations(), (current) =>
        current?.map((item) => (item.id === conversationId ? { ...item, pinned } : item)),
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
