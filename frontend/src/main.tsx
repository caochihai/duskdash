import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';
import { initializeAuthentication } from './auth/keycloak';

import './styles/reset.css';
import './styles/global.css';
import './styles/accessibility.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Không tìm thấy phần tử #root trong index.html');
}

async function bootstrap(): Promise<void> {
  await initializeAuthentication();
  createRoot(rootElement as HTMLElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void bootstrap().catch(() => {
  createRoot(rootElement).render(
    <div role="alert" style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>
      Không thể khởi tạo phiên đăng nhập. Vui lòng kiểm tra Keycloak và tải lại trang.
    </div>,
  );
});
