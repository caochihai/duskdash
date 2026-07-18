import {
  CONVERSATION_GROUP_LABEL,
  type Conversation,
  type ConversationGroup,
  type ConversationGroupKey,
} from '@/types/conversation';
import { getConversationGroup } from '@/utils/formatDate';
import { normalizeVietnamese } from '@/utils/detectSensitiveContent';

/** Thứ tự hiển thị các nhóm trong sidebar. */
const GROUP_ORDER: ConversationGroupKey[] = ['pinned', 'today', 'yesterday', 'last7Days', 'older'];

/**
 * Lọc hội thoại theo từ khoá tìm kiếm.
 * So khớp không dấu để "vay mua nha" tìm được "Tư vấn vay mua nhà".
 */
export function filterConversations(
  conversations: Conversation[],
  searchTerm: string,
): Conversation[] {
  const term = normalizeVietnamese(searchTerm);
  if (!term) return conversations;

  return conversations.filter((conversation) => {
    const haystack = normalizeVietnamese(`${conversation.title} ${conversation.preview ?? ''}`);
    return haystack.includes(term);
  });
}

/** Nhóm hội thoại theo thời gian, giữ nhóm "Đã ghim" lên đầu. */
export function groupConversations(
  conversations: Conversation[],
  now: Date = new Date(),
): ConversationGroup[] {
  const buckets = new Map<ConversationGroupKey, Conversation[]>();

  for (const conversation of conversations) {
    const key = getConversationGroup(conversation, now);
    const list = buckets.get(key) ?? [];
    list.push(conversation);
    buckets.set(key, list);
  }

  return GROUP_ORDER.flatMap((key) => {
    const items = buckets.get(key);
    if (!items?.length) return [];

    return [
      {
        key,
        label: CONVERSATION_GROUP_LABEL[key],
        items: items.sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt)),
      },
    ];
  });
}
