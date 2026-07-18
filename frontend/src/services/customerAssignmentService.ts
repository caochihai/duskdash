import apiClient, { USE_MOCK_API } from './apiClient';
import type { BackendAssignmentLease } from '@/types/backend';

const activeLeases = new Map<string, BackendAssignmentLease>();

export async function claimCustomerAssignment(
  customerId: string,
  expectedVersion: number,
): Promise<BackendAssignmentLease | undefined> {
  if (USE_MOCK_API) return undefined;
  const existing = activeLeases.get(customerId);
  if (existing && Date.parse(existing.lease_expires_at) > Date.now() + 30_000) return existing;

  const response = await apiClient.post<BackendAssignmentLease>(
    `/customers/${customerId}/assignment/claim`,
    { expected_version: expectedVersion },
  );
  activeLeases.set(customerId, response.data);
  return response.data;
}
