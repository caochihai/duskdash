import { useQuery } from '@tanstack/react-query';
import { listCustomers } from '@/services/customerService';

export function useCustomers() {
  return useQuery({
    queryKey: ['customers', 'search-options'],
    queryFn: ({ signal }) => listCustomers(signal),
    staleTime: 30_000,
  });
}
