import type { ChatSource } from './source';
import type { ChatAttachment } from './attachment';
import type { AgentTrace } from './agent';
import type { Customer, LoanApplication } from './customer';

export type MessageRole = 'user' | 'assistant' | 'system';

export type MessageStatus =
  | 'pending'
  | 'thinking'
  | 'streaming'
  | 'completed'
  | 'error'
  | 'stopped';

/**
 * Chế độ nghiệp vụ — quyết định agent nào được ưu tiên điều phối.
 * Người dùng là chuyên viên ngân hàng, nên chế độ theo NGHIỆP VỤ nội bộ,
 * không phải theo phân khúc khách hàng.
 */
export type ChatMode = 'general' | 'credit' | 'compliance' | 'operations' | 'document';

export const CHAT_MODE_LABEL: Record<ChatMode, string> = {
  general: 'Điều phối tự động',
  credit: 'Thẩm định tín dụng',
  compliance: 'Pháp chế & Tuân thủ',
  operations: 'Vận hành & Quy trình',
  document: 'Tra cứu tài liệu',
};

/**
 * Trạng thái xử lý cấp cao của AI.
 * CHỈ mô tả tiến trình an toàn — không phản ánh chain-of-thought nội bộ.
 */
export type AIProcessingPhase =
  | 'connecting'
  | 'understanding'
  | 'searching'
  | 'reading'
  | 'composing'
  | 'done';

export const AI_PHASE_LABEL: Record<AIProcessingPhase, string> = {
  connecting: 'Đang kết nối',
  understanding: 'Đang xác định nhu cầu của bạn',
  searching: 'Đang tra cứu thông tin phù hợp',
  reading: 'Đang đọc tài liệu',
  composing: 'Đang tổng hợp câu trả lời',
  done: 'Đã hoàn thành',
};

export interface ChatSuggestion {
  id: string;
  label: string;
  prompt: string;
}

/* ------------------------------------------------------------------ */
/* Rich content blocks                                                 */
/* ------------------------------------------------------------------ */

/**
 * Nội dung phong phú của câu trả lời AI được mô hình hoá thành union có kiểu
 * rõ ràng, thay vì nhúng HTML thô.
 *
 * Lý do: renderer dựng React element trực tiếp từ block, không dùng
 * `dangerouslySetInnerHTML` ở bất kỳ đâu → không có đường cho script injection.
 */

export interface MarkdownBlock {
  type: 'markdown';
  /** Markdown giới hạn: heading, list, table, quote, code, link, bold/italic. */
  content: string;
}

export interface TableBlock {
  type: 'table';
  title?: string;
  columns: Array<{ key: string; title: string; align?: 'left' | 'right' | 'center' }>;
  rows: Array<Record<string, string>>;
  /** Ghi chú nhỏ dưới bảng, ví dụ nhãn "dữ liệu minh hoạ". */
  footnote?: string;
}

export interface ChartDatum {
  category: string;
  value: number;
  series?: string;
}

export interface ChartBlock {
  type: 'chart';
  chartType: 'column' | 'line';
  title?: string;
  description?: string;
  data: ChartDatum[];
  /** Nhãn trục, dùng cho cả accessible description. */
  xLabel?: string;
  yLabel?: string;
  /** Định dạng giá trị: tiền tệ VNĐ hay số thường. */
  valueFormat?: 'currency' | 'number' | 'percent';
}

export interface LoanEstimateBlock {
  type: 'loanEstimate';
  amount: number;
  termYears: number;
  assumedRatePercent: number;
  method: string;
  /** Khoản trả hàng tháng ước tính (VNĐ). */
  monthlyPayment: number;
  totalInterest: number;
  totalPayment: number;
}

export interface ProductBlock {
  type: 'product';
  title: string;
  description: string;
  benefits: string[];
  badge?: string;
  primaryActionLabel: string;
  secondaryActionLabel?: string;
}

export interface AlertBlock {
  type: 'alert';
  variant: 'info' | 'warning' | 'success' | 'error';
  title?: string;
  content: string;
}

export interface CtaBlock {
  type: 'cta';
  actions: Array<{ id: string; label: string; primary?: boolean; prompt?: string }>;
}

export interface DisclaimerBlock {
  type: 'disclaimer';
  content: string;
}

/** Hồ sơ vay kèm nút phê duyệt — dành cho chuyên viên tín dụng. */
export interface LoanApprovalBlock {
  type: 'loanApproval';
  application: LoanApplication;
}

/** Tóm tắt hồ sơ khách hàng ngay trong luồng hội thoại. */
export interface CustomerSummaryBlock {
  type: 'customerSummary';
  customer: Customer;
}

export type MessageBlock =
  | MarkdownBlock
  | TableBlock
  | ChartBlock
  | LoanEstimateBlock
  | ProductBlock
  | AlertBlock
  | CtaBlock
  | DisclaimerBlock
  | LoanApprovalBlock
  | CustomerSummaryBlock;

/* ------------------------------------------------------------------ */
/* Message                                                             */
/* ------------------------------------------------------------------ */

export interface ChatMessage {
  id: string;
  conversationId: string;
  role: MessageRole;
  /** Nội dung text thuần — dùng cho streaming, sao chép và fallback. */
  content: string;
  status: MessageStatus;
  /** ISO 8601 */
  createdAt: string;
  /** Nội dung phong phú, chỉ xuất hiện khi status = 'completed'. */
  blocks?: MessageBlock[];
  sources?: ChatSource[];
  attachments?: ChatAttachment[];
  suggestions?: ChatSuggestion[];
  /** Phase hiện tại khi status = 'thinking'. */
  phase?: AIProcessingPhase;
  /**
   * Dấu vết phối hợp của hệ multi-agent cho câu trả lời này.
   * Hiển thị dưới dạng chuỗi bước có thể mở/đóng phía trên nội dung.
   */
  trace?: AgentTrace;
  /** Thông báo lỗi hiển thị cho người dùng khi status = 'error'. */
  errorMessage?: string;
}

export type MessageFeedback = 'helpful' | 'not-helpful';
