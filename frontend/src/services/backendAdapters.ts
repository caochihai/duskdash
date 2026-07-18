import type { ChatMessage } from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import type { ChatSource, SourceType } from '@/types/source';
import type {
  BackendCitation,
  BackendConversation,
  BackendConversationReply,
  BackendMessage,
} from '@/types/backend';

export function toConversation(
  value: BackendConversation,
  options: { pinned?: boolean } = {},
): Conversation {
  return {
    id: value.id,
    title: value.title?.trim() || 'Cuộc trò chuyện mới',
    createdAt: value.started_at,
    updatedAt: value.ended_at ?? value.started_at,
    pinned: options.pinned,
    customerId: value.active_customer_id ?? undefined,
    activeLoanApplicationId: value.active_loan_application_id ?? undefined,
    status: value.status,
  };
}

export function toChatMessage(
  value: BackendMessage,
  reply?: BackendConversationReply | null,
): ChatMessage {
  const sources = reply ? citationsToSources(reply.metadata.citations) : undefined;
  return {
    id: value.id,
    conversationId: value.conversation_id,
    role: value.sender_type.toUpperCase() === 'ASSISTANT' ? 'assistant' : 'user',
    content: value.content,
    status: 'completed',
    createdAt: value.created_at ?? new Date().toISOString(),
    ...(sources?.length ? { sources } : {}),
  };
}

function citationsToSources(value: unknown): ChatSource[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value
    .filter(isCitation)
    .map((citation) => ({
      id: `${citation.citation_type}:${citation.source_id}:${citation.number}`,
      title: `Nguồn [${citation.number}] – ${citation.source_type}`,
      type: citationSourceType(citation),
      excerpt: citation.quoted_text?.trim() || 'Nguồn tham chiếu được backend cung cấp.',
      url: safeCitationUrl(citation),
    }))
    .map(({ url, ...source }) => (url ? { ...source, url } : source));
}

function isCitation(value: unknown): value is BackendCitation {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<BackendCitation>;
  return (
    typeof item.number === 'number' &&
    typeof item.citation_type === 'string' &&
    typeof item.source_type === 'string' &&
    typeof item.source_id === 'string'
  );
}

function citationSourceType(citation: BackendCitation): SourceType {
  if (citation.citation_type === 'POLICY') return 'policy';
  if (citation.source_type.includes('DOCUMENT')) return 'attachment';
  if (citation.citation_type === 'CALCULATION') return 'procedure';
  return 'procedure';
}

function safeCitationUrl(citation: BackendCitation): string | undefined {
  const locator = citation.source_locator;
  if (!locator || locator.retrievable === false) return undefined;
  const candidate = locator.url ?? locator.api_path;
  if (typeof candidate !== 'string') return undefined;
  if (candidate.startsWith('/')) return candidate;
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? candidate : undefined;
  } catch {
    return undefined;
  }
}
