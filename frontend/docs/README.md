# SHB AI Assistant — Digital Expert Agents (SH-AI)

Hệ chuyên gia số đa agent phục vụ vận hành ngân hàng SHB — bản demo frontend.

Toàn bộ mã nguồn frontend nằm trong thư mục [`frontend/`](./frontend).

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
```

Xem chi tiết kiến trúc, tính năng, API contract và hướng dẫn tại
[`frontend/README.md`](./frontend/README.md).

## Công nghệ

Vite · React 19 · TypeScript · React Router 7 · Ant Design 6 · Ant Design X 2 ·
Ant Design Charts 2 · TanStack Query 5 · Axios · Motion for React · CSS Modules.

> ⚠️ Bản demo: không kết nối core banking, không thực hiện giao dịch thật.
> Toàn bộ dữ liệu khách hàng/hồ sơ là hư cấu.
