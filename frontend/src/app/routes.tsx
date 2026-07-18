import { lazy, Suspense } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router-dom';
import { LoadingScreen } from '@/components/common/LoadingScreen';
import { RequireAuth } from '@/auth/RequireAuth';
import ChatPage from '@/pages/ChatPage';

/**
 * Khai báo route TẬP TRUNG.
 * Không khai báo route rải rác trong component.
 *
 * - `/login`        : trang đăng nhập (route công khai duy nhất).
 * - `/` và `/chat`  : giao diện trò chuyện chính SH-AI.
 * - `/dashboard`    : bảng điều khiển agent.
 * - `/customer/:id` : hồ sơ chi tiết khách hàng.
 * - `/foundation`   : trang kiểm thử nền tảng.
 * - `*`             : trang không tìm thấy.
 *
 * Mọi route nghiệp vụ đều bọc RequireAuth: chưa đăng nhập sẽ được đưa về
 * `/login?returnTo=...` và quay lại đúng trang sau khi xác thực.
 */

// Lazy-load các trang phụ: chúng không nằm trên đường đi chính của người dùng.
const LoginPage = lazy(() => import('@/pages/LoginPage'));
const FoundationPage = lazy(() => import('@/pages/FoundationPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
const AgentDashboardPage = lazy(() => import('@/pages/AgentDashboardPage'));
const CustomerDetailPage = lazy(() => import('@/pages/CustomerDetailPage'));

function withSuspense(node: React.ReactNode) {
  return <Suspense fallback={<LoadingScreen message="Đang tải trang" />}>{node}</Suspense>;
}

function protectedPage(node: React.ReactNode) {
  return <RequireAuth>{node}</RequireAuth>;
}

export const routeObjects: RouteObject[] = [
  {
    path: '/login',
    element: withSuspense(<LoginPage />),
  },
  {
    path: '/',
    element: protectedPage(<ChatPage />),
  },
  {
    path: '/chat',
    element: protectedPage(<ChatPage />),
  },
  {
    path: '/dashboard',
    element: protectedPage(withSuspense(<AgentDashboardPage />)),
  },
  {
    path: '/customer/:id',
    element: protectedPage(withSuspense(<CustomerDetailPage />)),
  },
  {
    path: '/foundation',
    element: protectedPage(withSuspense(<FoundationPage />)),
  },
  {
    path: '*',
    element: withSuspense(<NotFoundPage />),
  },
];

export const router = createBrowserRouter(routeObjects);
