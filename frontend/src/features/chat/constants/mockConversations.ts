import type { Conversation } from '@/types/conversation';

/**
 * Hội thoại mẫu của CHUYÊN VIÊN NGÂN HÀNG — các tác vụ vận hành nội bộ
 * (thẩm định, tuân thủ, tra cứu quy trình), không phải câu hỏi của khách hàng.
 *
 * Timestamp tương đối tính từ lúc nạp module, để danh sách luôn phân bổ đúng
 * vào các nhóm Hôm nay / Hôm qua / 7 ngày qua / Trước đó.
 */
function hoursAgo(hours: number): string {
  return new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
}

function daysAgoIso(days: number, atHour = 10): string {
  const date = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  date.setHours(atHour, 0, 0, 0);
  return date.toISOString();
}

/** Hội thoại demo có sẵn kịch bản thẩm định hồ sơ vay đầy đủ. */
export const DEMO_LOAN_CONVERSATION_ID = 'conv-loan-review';

export const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: DEMO_LOAN_CONVERSATION_ID,
    title: 'Thẩm định hồ sơ HS-2026-0481',
    preview: 'Vay mua nhà 2 tỷ — Trần Thị Hồng Nhung — 5/5 chốt kiểm tra đạt',
    createdAt: hoursAgo(3),
    updatedAt: hoursAgo(1),
    pinned: true,
  },
  {
    id: 'conv-compliance-check',
    title: 'Kiểm tra tuân thủ Minh Phát',
    preview: 'Sàng lọc AML/KYC cho khách hàng doanh nghiệp',
    createdAt: hoursAgo(6),
    updatedAt: hoursAgo(4),
  },
  {
    id: 'conv-ltv-policy',
    title: 'Ngưỡng LTV và DTI hiện hành',
    preview: 'Tra cứu chính sách cấp tín dụng khách hàng cá nhân',
    createdAt: hoursAgo(9),
    updatedAt: hoursAgo(8),
  },
  {
    id: 'conv-car-loan-docs',
    title: 'HS-2026-0492 thiếu chứng từ',
    preview: 'Vay tiêu dùng — DTI 68% vượt ngưỡng, thiếu sao kê lương',
    createdAt: daysAgoIso(1, 15),
    updatedAt: daysAgoIso(1, 16),
  },
  {
    id: 'conv-guarantee-process',
    title: 'Quy trình bảo lãnh dự thầu',
    preview: 'Các bước phát hành và chứng từ bắt buộc',
    createdAt: daysAgoIso(1, 9),
    updatedAt: daysAgoIso(1, 10),
  },
  {
    id: 'conv-approval-authority',
    title: 'Đối chiếu hạn mức phê duyệt',
    preview: 'Phân cấp thẩm quyền theo giá trị khoản vay',
    createdAt: daysAgoIso(3),
    updatedAt: daysAgoIso(3, 14),
  },
  {
    id: 'conv-trade-finance',
    title: 'Tài trợ thương mại xuất khẩu',
    preview: 'HS-2026-0455 — bổ sung vốn lưu động 5 tỷ',
    createdAt: daysAgoIso(5),
    updatedAt: daysAgoIso(5, 11),
  },
  {
    id: 'conv-aml-screening',
    title: 'Sàng lọc AML khách hàng mới',
    preview: 'Quy trình định danh và đối chiếu danh sách cảnh báo',
    createdAt: daysAgoIso(12),
    updatedAt: daysAgoIso(12, 15),
  },
  {
    id: 'conv-lending-rate',
    title: 'Biểu lãi suất cho vay tham khảo',
    preview: 'Mức lãi suất theo từng chương trình và kỳ điều chỉnh',
    createdAt: daysAgoIso(21),
    updatedAt: daysAgoIso(20, 9),
  },
];
