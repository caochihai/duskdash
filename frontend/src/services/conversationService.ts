import apiClient, { USE_MOCK_API } from './apiClient';
import {
  mockCreateConversation,
  mockDeleteConversation,
  mockGetConversation,
  mockListConversations,
  mockUpdateConversation,
} from './mockApi';
import type { Conversation } from '@/types/conversation';
import type {
  CreateConversationResponse,
  GetConversationResponse,
  GetConversationsResponse,
  UpdateConversationRequest,
  UpdateConversationResponse,
} from '@/types/api';

/**
 * Service hội thoại — lớp duy nhất quyết định dùng mock hay backend thật.
 * Hook và component không cần biết đang ở chế độ nào.
 */

export async function listConversations(signal?: AbortSignal): Promise<Conversation[]> {
  if (USE_MOCK_API) return mockListConversations(signal);

  const response = await apiClient.get<GetConversationsResponse>('/conversations', { signal });
  return response.data.data;
}

export async function getConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<Conversation> {
  if (USE_MOCK_API) return mockGetConversation(conversationId, signal);

  const response = await apiClient.get<GetConversationResponse>(
    `/conversations/${conversationId}`,
    { signal },
  );
  return response.data.data;
}

export interface CreateConversationInput {
  title?: string;
  customerId?: string;
  customerName?: string;
}

export async function createConversation(
  input: CreateConversationInput = {},
): Promise<Conversation> {
  if (USE_MOCK_API) return mockCreateConversation(input);

  const response = await apiClient.post<CreateConversationResponse>('/conversations', input);
  return response.data.data;
}

export async function updateConversation(
  conversationId: string,
  patch: UpdateConversationRequest,
): Promise<Conversation> {
  if (USE_MOCK_API) return mockUpdateConversation(conversationId, patch);

  const response = await apiClient.patch<UpdateConversationResponse>(
    `/conversations/${conversationId}`,
    patch,
  );
  return response.data.data;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  if (USE_MOCK_API) return mockDeleteConversation(conversationId);

  await apiClient.delete(`/conversations/${conversationId}`);
}
