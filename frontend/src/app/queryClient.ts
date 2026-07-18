import { QueryClient } from '@tanstack/react-query';
import { normalizeError } from '@/services/apiClient';
import { API_ERROR_CODES } from '@/types/api';

/**
 * QueryClient dùng chung.
 *
 * Lưu ý: client này CHỈ quản lý server state (hội thoại, tin nhắn, upload).
 * Trạng thái UI cục bộ (sidebar, drawer, modal, input, hover) dùng React state.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,

      /**
       * Retry có kiểm soát: không thử lại với lỗi do client gây ra
       * (404 / 401 / 422) vì thử lại cũng không thể thành công.
       */
      retry: (failureCount, error) => {
        const apiError = normalizeError(error);
        const noRetryCodes: string[] = [
          API_ERROR_CODES.notFound,
          API_ERROR_CODES.unauthorized,
          API_ERROR_CODES.validation,
        ];
        if (noRetryCodes.includes(apiError.code)) return false;
        return failureCount < 1;
      },

      retryDelay: (attemptIndex) => Math.min(1_000 * 2 ** attemptIndex, 5_000),
    },

    mutations: {
      retry: 0,
    },
  },
});
