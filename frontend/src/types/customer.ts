import type { AgentRole } from './agent';

export type CustomerSegment = 'personal' | 'business';

/** Nhãn phân khúc khách hàng (khác với vai trò nhân viên trong `user.ts`). */
export const SEGMENT_LABEL: Record<CustomerSegment, string> = {
  personal: 'Khách hàng cá nhân',
  business: 'Khách hàng doanh nghiệp',
};

export type RiskLevel = 'low' | 'medium' | 'high';

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: 'Rủi ro thấp',
  medium: 'Rủi ro trung bình',
  high: 'Rủi ro cao',
};

/**
 * Hồ sơ khách hàng mà chuyên viên tra cứu.
 *
 * Lưu ý: các trường định danh (CCCD, số điện thoại) được lưu ở dạng ĐÃ CHE
 * ngay trong mock data — frontend demo không bao giờ giữ dữ liệu định danh đầy đủ.
 */
export interface Customer {
  id: string;
  /** Mã CIF nội bộ. */
  code: string;
  fullName: string;
  segment: CustomerSegment;
  /** Đã che, ví dụ "0•••••••234". */
  idNumberMasked: string;
  phoneMasked: string;
  branch: string;
  /** Ngày trở thành khách hàng (ISO). */
  customerSince: string;
  creditScore: number;
  riskLevel: RiskLevel;
  monthlyIncome: number;
  existingDebt: number;
  /** Debt-to-income, %. */
  dti: number;
  /** False when the list API did not return financial metrics; UI renders a dash. */
  metricsAvailable?: boolean;
  assignmentVersion?: number;
}

export type LoanApplicationStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'need-info'
  | 'closed';

export const LOAN_STATUS_LABEL: Record<LoanApplicationStatus, string> = {
  pending: 'Chờ phê duyệt',
  approved: 'Đã phê duyệt',
  rejected: 'Đã từ chối',
  'need-info': 'Cần bổ sung hồ sơ',
  closed: 'Đã tất toán',
};

/** Màu Tag theo trạng thái — dùng thống nhất mọi nơi. */
export const LOAN_STATUS_COLOR: Record<LoanApplicationStatus, string> = {
  pending: 'orange',
  approved: 'green',
  rejected: 'red',
  'need-info': 'gold',
  closed: 'default',
};

/** Kết quả kiểm tra của một agent chuyên môn đối với hồ sơ vay. */
export interface LoanCheck {
  agent: AgentRole;
  label: string;
  passed: boolean;
  note: string;
}

export interface LoanApplication {
  id: string;
  /** Mã hồ sơ, ví dụ "HS-2026-0481". */
  code: string;
  customerId: string;
  customerName: string;
  productName: string;
  amount: number;
  termYears: number;
  ratePercent: number;
  purpose: string;
  collateralValue: number;
  /** Loan-to-value, %. */
  ltv: number;
  status: LoanApplicationStatus;
  submittedAt: string;
  checks: LoanCheck[];
  /** Hạn mức phê duyệt của chuyên viên đang đăng nhập (VNĐ). */
  approvalLimit: number;
}
