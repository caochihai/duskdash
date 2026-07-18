import { lazy, Suspense } from 'react';
import { createBrowserRouter, type RouteObject } from 'react-router-dom';
import { LoadingScreen } from '@/components/common/LoadingScreen';
import ChatPage from '@/pages/ChatPage';

/**
 * Khai báo route TẬP TRUNG.
 * Không khai báo route rải rác trong component.
 *
 * - `/`  : giao diện chính SH-AI.
 *          Query param `?view=foundation` hiển thị FoundationPage (kiểm thử nền tảng).
 * - `*`  : trang không tìm thấy.
 */

// Lazy-load các trang phụ: chúng không nằm trên đường đi chính của người dùng.
const FoundationPage = lazy(() => import('@/pages/FoundationPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
const AgentDashboardPage = lazy(() => import('@/pages/AgentDashboardPage'));
const CustomerDetailPage = lazy(() => import('@/pages/CustomerDetailPage'));

function withSuspense(node: React.ReactNode) {
  return <Suspense fallback={<LoadingScreen message="Đang tải trang" />}>{node}</Suspense>;
}

export const routeObjects: RouteObject[] = [
  {
    path: '/',
    element: <ChatPage />,
  },
  {
    path: '/dashboard',
    element: withSuspense(<AgentDashboardPage />),
  },
  {
    path: '/customer/:id',
    element: withSuspense(<CustomerDetailPage />),
  },
  {
    path: '/foundation',
    element: withSuspense(<FoundationPage />),
  },
  {
    path: '*',
    element: withSuspense(<NotFoundPage />),
  },
];

export const router = createBrowserRouter(routeObjects);
