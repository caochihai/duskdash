import { useQuery } from '@tanstack/react-query';
import { listCustomers } from '@/services/customerService';
import { useDemoSession } from '@/auth/demoSession';

export function useCustomers() {
  // Danh mục khách hàng phụ thuộc phạm vi được phân công, nên phiên đăng nhập
  // phải nằm trong queryKey: đổi tài khoản là đổi kết quả, không dùng lại cache.
  const session = useDemoSession();

  return useQuery({
    queryKey: ['customers', 'search-options', session?.username ?? 'anonymous'],
    queryFn: ({ signal }) => listCustomers(signal),
    staleTime: 30_000,
  });
}
