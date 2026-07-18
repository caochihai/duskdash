/**
 * Người dùng của ứng dụng là NHÂN VIÊN NGÂN HÀNG (nội bộ SHB), không phải
 * khách hàng — theo đề bài "Digital Expert Agents for Banking Operations".
 *
 * Phân khúc khách hàng (`CustomerSegment`) là khái niệm khác, nằm ở `customer.ts`.
 */

export type StaffRole = 'credit-officer' | 'approver' | 'compliance' | 'operations';

export const STAFF_ROLE_LABEL: Record<StaffRole, string> = {
  'credit-officer': 'Chuyên viên Tín dụng',
  approver: 'Cấp phê duyệt',
  compliance: 'Pháp chế & Tuân thủ',
  operations: 'Vận hành',
};

export interface UserProfile {
  id: string;
  displayName: string;
  role: StaffRole;
  /** Phòng ban / đơn vị công tác. */
  department: string;
  branch: string;
  /** Hạn mức phê duyệt (VNĐ) — quyết định nút "Phê duyệt" có bị khoá không. */
  approvalLimit: number;
  avatarUrl?: string;
}
