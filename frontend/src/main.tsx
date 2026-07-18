import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './app/App';

import './styles/reset.css';
import './styles/global.css';
import './styles/accessibility.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Không tìm thấy phần tử #root trong index.html');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
