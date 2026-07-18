import { useQuery } from '@tanstack/react-query';
import { listConversations } from '@/services/conversationService';
import { chatQueryKeys } from './queryKeys';

/** Danh sách hội thoại cho sidebar. */
export function useConversations() {
  return useQuery({
    queryKey: chatQueryKeys.conversations(),
    queryFn: ({ signal }) => listConversations(signal),
    staleTime: 30_000,
  });
}
