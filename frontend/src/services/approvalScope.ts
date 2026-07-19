import { getDemoSession } from '@/auth/demoSession';
import type { LoanApplication } from '@/types/customer';

/**
 * Áp hạn mức phê duyệt của CHUYÊN VIÊN ĐANG ĐĂNG NHẬP lên hồ sơ vay.
 *
 * Dữ liệu mock mang sẵn một hạn mức mặc định; hạn mức thật là thuộc tính của
 * người dùng, không của hồ sơ. Gộp ở đây để `LoanApprovalCard` chỉ cần đọc
 * `application.approvalLimit` và tự khoá nút phê duyệt khi vượt thẩm quyền.
 */
export function applyApprovalLimit(application: LoanApplication): LoanApplication {
  const limit = getDemoSession()?.profile.approvalLimit;
  if (limit === undefined || limit === application.approvalLimit) return application;
  return { ...application, approvalLimit: limit };
}

export function applyApprovalLimitAll(applications: LoanApplication[]): LoanApplication[] {
  return applications.map(applyApprovalLimit);
}
