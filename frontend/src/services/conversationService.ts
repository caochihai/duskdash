import apiClient, { USE_MOCK_API } from './apiClient';
import {
  mockCreateConversation,
  mockDeleteConversation,
  mockGetConversation,
  mockListConversations,
  mockUpdateConversation,
} from './mockApi';
import type { Conversation } from '@/types/conversation';
import type { UpdateConversationRequest } from '@/types/api';
import type { BackendConversation } from '@/types/backend';
import { toConversation } from './backendAdapters';

/**
 * Service hội thoại — lớp duy nhất quyết định dùng mock hay backend thật.
 * Hook và component không cần biết đang ở chế độ nào.
 */

export async function listConversations(signal?: AbortSignal): Promise<Conversation[]> {
  if (USE_MOCK_API) return mockListConversations(signal);

  const response = await apiClient.get<BackendConversation[]>('/conversations', {
    signal,
    params: { status: 'ACTIVE' },
  });
  return response.data.map((item) =>
    toConversation(item, { pinned: pinnedConversationIds.has(item.id) }),
  );
}

export async function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<Conversation> {
  if (USE_MOCK_API) return mockGetConversation(conversationId, signal);

  const response = await apiClient.get<BackendConversation>(`/conversations/${conversationId}`, {
    signal,
  });
  return toConversation(response.data, { pinned: pinnedConversationIds.has(conversationId) });
}

export interface CreateConversationInput {
  title?: string;
  customerId?: string;
  customerName?: string;
  loanApplicationId?: string;
}

export async function createConversation(
  input: CreateConversationInput = {},
): Promise<Conversation> {
  if (USE_MOCK_API) return mockCreateConversation(input);

  const title = input.title?.trim() || (input.customerName ? `KH: ${input.customerName}` : undefined);
  const response = await apiClient.post<BackendConversation>('/conversations', {
    title,
    active_customer_id: input.customerId,
    active_loan_application_id: input.loanApplicationId,
  });
  return toConversation(response.data);
}

export async function updateConversation(
  conversationId: string,
  patch: UpdateConversationRequest,
): Promise<Conversation> {
  if (USE_MOCK_API) return mockUpdateConversation(conversationId, patch);

  if (patch.pinned !== undefined) {
    if (patch.pinned) pinnedConversationIds.add(conversationId);
    else pinnedConversationIds.delete(conversationId);
  }

  const response = patch.title
    ? await apiClient.patch<BackendConversation>(`/conversations/${conversationId}`, {
        title: patch.title,
      })
    : await apiClient.get<BackendConversation>(`/conversations/${conversationId}`);
  return toConversation(response.data, { pinned: pinnedConversationIds.has(conversationId) });
}

/** Gắn khách hàng vào hội thoại đang mở (vd: khách nháp backend vừa tạo từ upload). */
export async function setConversationCustomer(
  conversationId: string,
  customerId: string,
): Promise<void> {
  if (USE_MOCK_API) return;
  await apiClient.patch(`/conversations/${conversationId}`, {
    active_customer_id: customerId,
  });
}

export async function deleteConversation(conversationId: string): Promise<void> {
  if (USE_MOCK_API) return mockDeleteConversation(conversationId);

  await apiClient.post(`/conversations/${conversationId}/close`);
  pinnedConversationIds.delete(conversationId);
}

// The fixed database contract has no pinned column. Keep this UI-only preference
// in memory and never persist conversation identifiers in browser storage.
const pinnedConversationIds = new Set<string>();
