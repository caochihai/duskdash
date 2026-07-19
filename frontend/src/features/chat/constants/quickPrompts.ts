import {
  AuditOutlined,
  BankOutlined,
  FileSearchOutlined,
  SafetyCertificateOutlined,
  SolutionOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { ComponentType } from 'react';

export interface QuickPrompt {
  id: string;
  title: string;
  description: string;
  /** Icon component từ @ant-design/icons — nguồn icon duy nhất của dự án. */
  icon: ComponentType;
  /** Câu hỏi thực tế được gửi khi chuyên viên chọn thẻ. */
  prompt: string;
  /** Số liệu nổi bật (ví dụ số hồ sơ đang chờ). */
  badge?: string;
}

/**
 * Quick prompt dành cho CHUYÊN VIÊN NGÂN HÀNG.
 *
 * Đây là các tác vụ vận hành nội bộ (thẩm định, tra cứu, tuân thủ), không phải
 * câu hỏi của khách hàng cuối.
 */
export const QUICK_PROMPTS: readonly QuickPrompt[] = [
  {
    id: 'pending-approvals',
    title: 'Hồ sơ chờ duyệt',
    description: 'Danh sách hồ sơ vay đang chờ quyết định',
    icon: AuditOutlined,
    prompt: 'Liệt kê các hồ sơ vay đang chờ phê duyệt của tôi.',
    badge: '3',
  },
  {
    id: 'loan-review',
    title: 'Thẩm định khoản vay',
    description: 'Điều phối các chuyên gia số thẩm định hồ sơ',
    icon: SolutionOutlined,
    prompt: 'Thẩm định hồ sơ vay HS-2026-0481.',
  },
  {
    id: 'customer-lookup',
    title: 'Tra cứu khách hàng',
    description: 'Xem hồ sơ tín dụng và quan hệ giao dịch',
    icon: UserOutlined,
    prompt: 'Cho tôi thông tin khách hàng Trần Thị Hồng Nhung (CIF-8842019).',
  },
  {
    id: 'compliance-check',
    title: 'Kiểm tra tuân thủ',
    description: 'Sàng lọc AML/KYC và rủi ro pháp lý',
    icon: SafetyCertificateOutlined,
    prompt: 'Kiểm tra tuân thủ AML/KYC cho khách hàng Công ty CP Bao bì VinaNova.',
  },
  {
    id: 'process-lookup',
    title: 'Tra cứu quy trình',
    description: 'Các bước và chứng từ theo quy trình nghiệp vụ',
    icon: FileSearchOutlined,
    prompt: 'Quy trình phát hành bảo lãnh dự thầu gồm những bước nào?',
  },
  {
    id: 'credit-policy',
    title: 'Chính sách tín dụng',
    description: 'Ngưỡng LTV, DTI và điều kiện áp dụng',
    icon: BankOutlined,
    prompt: 'Ngưỡng LTV và DTI hiện hành cho sản phẩm vay mua nhà là bao nhiêu?',
  },
];
