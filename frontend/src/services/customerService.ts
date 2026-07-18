import apiClient, { USE_MOCK_API } from './apiClient';
import { MOCK_CUSTOMERS } from '@/features/chat/constants/mockCustomers';
import type { Customer, RiskLevel } from '@/types/customer';
import type {
  BackendCustomer,
  BackendLoanApplication,
  BackendPage,
} from '@/types/backend';

interface BackendMe {
  employee_id: string;
}

export async function listCustomers(signal?: AbortSignal): Promise<Customer[]> {
  if (USE_MOCK_API) return MOCK_CUSTOMERS;

  const response = await apiClient.get<BackendPage<BackendCustomer>>('/customers', {
    signal,
    params: { page: 1, page_size: 200 },
  });
  return response.data.items.map(toCustomer);
}

/** Select only a loan that the backend says is assigned to the current employee. */
export async function getAssignedLoanApplicationId(customerId: string): Promise<string | undefined> {
  if (USE_MOCK_API) return undefined;

  const [me, loans] = await Promise.all([
    apiClient.get<BackendMe>('/me'),
    apiClient.get<BackendLoanApplication[]>(`/customers/${customerId}/loan-applications`),
  ]);
  return loans.data.find(
    (loan) =>
      loan.assigned_employee_id === me.data.employee_id &&
      !['CLOSED', 'REJECTED', 'APPROVED'].includes(loan.status.toUpperCase()),
  )?.id;
}

function toCustomer(value: BackendCustomer): Customer {
  const customerId = value.id ?? value.customer_id;
  if (!customerId) throw new Error('Backend customer response is missing its identifier.');

  return {
    id: customerId,
    code: value.customer_number,
    fullName: value.full_name ?? value.display_name ?? `Khách hàng ${value.customer_number}`,
    segment: normalizeSegment(value.customer_segment),
    idNumberMasked: '—',
    phoneMasked: '—',
    branch: `CN ${value.home_branch_id.slice(0, 8)}`,
    customerSince: value.updated_at,
    creditScore: 0,
    riskLevel: normalizeRisk(value.risk_rating),
    monthlyIncome: 0,
    existingDebt: 0,
    dti: 0,
    metricsAvailable: false,
    assignmentVersion: value.version,
  };
}

function normalizeSegment(value?: string | null): Customer['segment'] {
  const normalized = value?.toUpperCase() ?? '';
  return normalized.includes('BUSINESS') || normalized.includes('CORPORATE')
    ? 'business'
    : 'personal';
}

function normalizeRisk(value?: string | null): RiskLevel {
  const normalized = value?.toUpperCase() ?? '';
  if (normalized.includes('HIGH')) return 'high';
  if (normalized.includes('LOW')) return 'low';
  return 'medium';
}
