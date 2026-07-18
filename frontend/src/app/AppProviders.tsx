import { QueryClientProvider } from '@tanstack/react-query';
import { App as AntdApp, ConfigProvider } from 'antd';
import viVN from 'antd/locale/vi_VN';
import { RouterProvider } from 'react-router-dom';
import { queryClient } from './queryClient';
import { router } from './routes';
import { shbTheme } from '@/theme';

/**
 * Tích hợp toàn bộ provider ở MỘT nơi duy nhất:
 * - QueryClientProvider : server state
 * - ConfigProvider      : theme SHB + locale tiếng Việt
 * - AntdApp             : context cho message / notification / modal
 * - RouterProvider      : routing
 */
export function AppProviders() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={shbTheme} locale={viVN}>
        <AntdApp
          notification={{ placement: 'topRight', duration: 4 }}
          message={{ duration: 2.5, maxCount: 3 }}
        >
          <RouterProvider router={router} />
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
