import { Navigate, useLocation } from 'react-router-dom';
import { isAuthenticated } from './keycloak';

/** Chặn route cần đăng nhập: chưa có phiên thì đưa về /login kèm đường quay lại. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  if (!isAuthenticated()) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?returnTo=${returnTo}`} replace />;
  }

  return <>{children}</>;
}
