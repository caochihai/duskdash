import type { UserProfile } from '@/types/user';

/**
 * Tài khoản demo — CHỈ dùng cho bản trình diễn chạy với `VITE_USE_MOCK_API`.
 *
 * Khi cắm Keycloak thật (`VITE_USE_MOCK_API=false`), toàn bộ file này không
 * được dùng tới: `isAuthenticated()` sẽ đọc phiên OIDC thay vì phiên demo.
 * Vì vậy mật khẩu ở đây KHÔNG phải bí mật thật và không mở đường vào dữ liệu
 * thật — mọi dữ liệu phía sau đều là mock trong bộ nhớ trình duyệt.
 *
 * Mỗi tài khoản mang một `authorizedCustomerIds` riêng: đây là bản thu nhỏ của
 * `AuthorizedScope` ở Engine (xem `libs/contracts/analysis.py`), để phần demo
 * thể hiện được nguyên tắc "chuyên viên chỉ thấy khách hàng được phân công".
 */
export interface DemoAccount {
  username: string;
  password: string;
  profile: UserProfile;
  /** Phạm vi khách hàng được phép xem — ánh xạ `AuthorizedScope.customer_ids`. */
  authorizedCustomerIds: string[];
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    username: 'chuyenvien1',
    password: 'chuyenvien1',
    profile: {
      id: 'staff-cv1',
      displayName: 'Nguyễn Minh Anh',
      role: 'credit-officer',
      department: 'Khối Tín dụng',
      branch: 'CN Hà Nội',
      approvalLimit: 3_000_000_000,
    },
    authorizedCustomerIds: ['cus-001', 'cus-002', 'cus-003'],
  },
  {
    username: 'chuyenvien2',
    password: 'chuyenvien2',
    profile: {
      id: 'staff-cv2',
      displayName: 'Trần Quốc Bảo',
      role: 'credit-officer',
      department: 'Khối Khách hàng Doanh nghiệp',
      branch: 'CN Hồ Chí Minh',
      approvalLimit: 1_500_000_000,
    },
    authorizedCustomerIds: ['cus-004', 'cus-005', 'cus-006'],
  },
];

/** Gợi ý hiển thị trên trang đăng nhập để người xem demo bấm điền nhanh. */
export const DEMO_ACCOUNT_HINTS = DEMO_ACCOUNTS.map((account) => ({
  username: account.username,
  password: account.password,
  displayName: account.profile.displayName,
  department: account.profile.department,
  branch: account.profile.branch,
  customerCount: account.authorizedCustomerIds.length,
}));

export function findDemoAccount(username: string, password: string): DemoAccount | null {
  const normalized = username.trim().toLowerCase();
  return (
    DEMO_ACCOUNTS.find(
      (account) => account.username === normalized && account.password === password,
    ) ?? null
  );
}
