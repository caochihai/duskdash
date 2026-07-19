import type { ChatMessage } from '@/types/chat';
import type { DocumentRegion } from '@/types/highlight';
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
  const metadata = reply?.metadata ?? (value as { metadata?: Record<string, unknown> }).metadata;
  const highlightDocuments = toHighlightDocuments(
    metadata?.highlight_documents,
    metadata?.highlight_segments,
  );
  const suggestions = toSuggestions(metadata?.suggested_questions);
  return {
    id: value.id,
    conversationId: value.conversation_id,
    role: value.sender_type.toUpperCase() === 'ASSISTANT' ? 'assistant' : 'user',
    content: value.content,
    status: 'completed',
    createdAt: value.created_at ?? new Date().toISOString(),
    ...(sources?.length ? { sources } : {}),
    ...(highlightDocuments?.length ? { highlightDocuments } : {}),
    ...(suggestions?.length ? { suggestions } : {}),
  };
}

const SEGMENT_LEVEL_BADGE: Record<string, string> = {
  critical: '🔴 CẢNH BÁO',
  warning: '🟠 CẦN CHÚ Ý',
  emphasis: '🟡 NHẤN MẠNH',
  pass: '✅ ĐẠT ĐIỀU KIỆN',
};

interface RawHighlightSegment {
  document_index?: number;
  text?: string;
  level?: string;
  reason?: string;
  legal_basis?: string | null;
  bbox_2d?: number[] | null;
}

/**
 * Đổi highlight_segments (bbox thang 0-1000 từ vision) thành vùng dẫn chứng
 * 0..1 cho viewer. Toạ độ dọc của model đáng tin; toạ độ ngang hay lệch nên
 * vẽ dải gần full chiều ngang theo dòng (khớp cách server vẽ lên ảnh).
 */
function segmentsToRegions(value: unknown): Map<number, DocumentRegion[]> {
  const byDocument = new Map<number, DocumentRegion[]>();
  if (!Array.isArray(value)) return byDocument;
  (value as RawHighlightSegment[]).forEach((segment, index) => {
    const bbox = segment?.bbox_2d;
    if (!Array.isArray(bbox) || bbox.length !== 4) return;
    const [, y1, , y2] = bbox;
    const top = Math.max(0, Math.min(y1, y2) / 1000 - 0.005);
    const height = Math.max(0.014, Math.abs(y2 - y1) / 1000 + 0.01);
    const documentIndex = typeof segment.document_index === 'number' ? segment.document_index : 0;
    const badge = SEGMENT_LEVEL_BADGE[segment.level ?? ''] ?? segment.level ?? '';
    const label = [badge, segment.reason, segment.legal_basis ? `⚖️ ${segment.legal_basis}` : '']
      .filter(Boolean)
      .join(' — ');
    const regions = byDocument.get(documentIndex) ?? [];
    regions.push({
      id: `seg-${index}`,
      x: 0.02,
      y: top,
      w: 0.96,
      h: Math.min(height, 1 - top),
      quote: segment.text ?? '',
      label,
    });
    byDocument.set(documentIndex, regions);
  });
  return byDocument;
}

/** Ảnh hồ sơ đã vẽ khung highlight từ metadata của responder. */
function toHighlightDocuments(
  value: unknown,
  segments: unknown,
): ChatMessage['highlightDocuments'] {
  if (!Array.isArray(value)) return undefined;
  const regionsByDocument = segmentsToRegions(segments);
  return value
    .filter(
      (item): item is { name?: string; url: string; index?: number } =>
        Boolean(item) && typeof item === 'object' && typeof (item as { url?: unknown }).url === 'string',
    )
    .map((item, position) => {
      const documentIndex = typeof item.index === 'number' ? item.index : position;
      return {
        name: typeof item.name === 'string' ? item.name : `Hồ sơ ${position + 1} (đã highlight)`,
        url: item.url,
        regions: regionsByDocument.get(documentIndex) ?? [],
      };
    });
}

/** Câu hỏi gợi ý do agent sinh — thành nút bấm-để-hỏi. */
function toSuggestions(value: unknown): ChatMessage['suggestions'] {
  if (!Array.isArray(value)) return undefined;
  return value
    .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    .slice(0, 5)
    .map((question, index) => ({
      id: `ai-suggest-${index}`,
      label: question,
      prompt: question,
    }));
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
