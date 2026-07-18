import type {
  AIProcessingPhase,
  ChatMessage,
  ChatMode,
  ChatSuggestion,
  MessageBlock,
} from '@/types/chat';
import type { Conversation } from '@/types/conversation';
import type { ChatAttachment } from '@/types/attachment';
import type { ApiError, StreamEvent } from '@/types/api';
import { API_ERROR_CODES } from '@/types/api';
import { ATTACHMENT_LIMITS, ACCEPTED_MIME_TYPES } from '@/types/attachment';
import { MOCK_CONVERSATIONS } from '@/features/chat/constants/mockConversations';
import {
  MOCK_LOAN_SOURCES,
  MOCK_LOAN_SUGGESTIONS,
  MOCK_MESSAGES_BY_CONVERSATION,
} from '@/features/chat/constants/mockMessages';
import { calculateAnnuityLoan } from '@/features/chat/utils/loanCalculator';
import { formatCurrency } from '@/utils/formatCurrency';
import { normalizeVietnamese } from '@/utils/detectSensitiveContent';
import type { AgentTrace } from '@/types/agent';
import {
  MOCK_CUSTOMERS,
  MOCK_LOAN_APPLICATIONS,
  findLoanByCustomer,
} from '@/features/chat/constants/mockCustomers';

/**
 * Mock API — cho phép toàn bộ frontend demo chạy khi chưa có backend.
 * Kích hoạt bằng `VITE_USE_MOCK_API=true`.
 *
 * Toàn bộ dữ liệu nằm trong bộ nhớ, mất khi refresh trang. Đây là chủ ý:
 * không lưu nội dung hội thoại vào localStorage vì có thể chứa dữ liệu nhạy cảm.
 */

/* ------------------------------------------------------------------ */
/* Tiện ích                                                            */
/* ------------------------------------------------------------------ */

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(createAbortError());
      return;
    }

    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);

    function onAbort() {
      clearTimeout(timer);
      reject(createAbortError());
    }

    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

function createAbortError(): DOMException {
  return new DOMException('Aborted', 'AbortError');
}

function randomBetween(min: number, max: number): number {
  return Math.round(min + Math.random() * (max - min));
}

function createId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowIso(): string {
  return new Date().toISOString();
}

function apiError(code: string, message: string): ApiError {
  return { code, message };
}

/* ------------------------------------------------------------------ */
/* Store trong bộ nhớ                                                  */
/* ------------------------------------------------------------------ */

const conversations: Conversation[] = MOCK_CONVERSATIONS.map((item) => ({ ...item }));

const messagesByConversation = new Map<string, ChatMessage[]>(
  Object.entries(MOCK_MESSAGES_BY_CONVERSATION).map(([id, list]) => [
    id,
    list.map((message) => ({ ...message })),
  ]),
);

/* ------------------------------------------------------------------ */
/* Trigger mô phỏng lỗi (chỉ dùng để demo error state)                 */
/* ------------------------------------------------------------------ */

const ERROR_TRIGGERS = {
  generic: 'mo phong loi',
  timeout: 'mo phong timeout',
  network: 'mo phong mat ket noi',
} as const;

function detectErrorTrigger(content: string): ApiError | null {
  const normalized = normalizeVietnamese(content);

  if (normalized.includes(ERROR_TRIGGERS.timeout)) {
    return apiError(API_ERROR_CODES.timeout, 'Yêu cầu mất quá nhiều thời gian. Vui lòng thử lại.');
  }
  if (normalized.includes(ERROR_TRIGGERS.network)) {
    return apiError(
      API_ERROR_CODES.network,
      'Không thể kết nối tới máy chủ. Vui lòng kiểm tra kết nối mạng.',
    );
  }
  if (normalized.includes(ERROR_TRIGGERS.generic)) {
    return apiError(
      API_ERROR_CODES.server,
      'Hệ thống đang bận nên chưa thể tạo câu trả lời. Vui lòng thử lại.',
    );
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Conversations                                                       */
/* ------------------------------------------------------------------ */

export async function mockListConversations(signal?: AbortSignal): Promise<Conversation[]> {
  await delay(randomBetween(250, 500), signal);
  return conversations
    .map((item) => ({ ...item }))
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt));
}

export async function mockGetConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<Conversation> {
  await delay(randomBetween(150, 300), signal);
  const found = conversations.find((item) => item.id === conversationId);
  if (!found) {
    throw apiError(API_ERROR_CODES.notFound, 'Không tìm thấy cuộc trò chuyện này.');
  }
  return { ...found };
}

export interface CreateConversationInput {
  title?: string;
  customerId?: string;
  customerName?: string;
}

export async function mockCreateConversation(
  input: CreateConversationInput = {},
  signal?: AbortSignal,
): Promise<Conversation> {
  await delay(randomBetween(200, 400), signal);

  const conversation: Conversation = {
    id: createId('conv'),
    title:
      input.title?.trim() ||
      (input.customerName ? `KH: ${input.customerName}` : 'Cuộc trò chuyện mới'),
    createdAt: nowIso(),
    updatedAt: nowIso(),
    ...(input.customerId ? { customerId: input.customerId } : {}),
    ...(input.customerName ? { customerName: input.customerName } : {}),
  };

  conversations.unshift(conversation);
  messagesByConversation.set(conversation.id, []);

  return { ...conversation };
}

export async function mockUpdateConversation(
  conversationId: string,
  patch: { title?: string; pinned?: boolean },
  signal?: AbortSignal,
): Promise<Conversation> {
  await delay(randomBetween(180, 350), signal);

  const index = conversations.findIndex((item) => item.id === conversationId);
  if (index === -1) {
    throw apiError(API_ERROR_CODES.notFound, 'Không tìm thấy cuộc trò chuyện này.');
  }

  if (patch.title !== undefined && !patch.title.trim()) {
    throw apiError(API_ERROR_CODES.validation, 'Tên cuộc trò chuyện không được để trống.');
  }

  const updated: Conversation = {
    ...conversations[index],
    ...(patch.title !== undefined ? { title: patch.title.trim() } : {}),
    ...(patch.pinned !== undefined ? { pinned: patch.pinned } : {}),
  };

  conversations[index] = updated;
  return { ...updated };
}

export async function mockDeleteConversation(
  conversationId: string,
  signal?: AbortSignal,
): Promise<void> {
  await delay(randomBetween(200, 400), signal);

  const index = conversations.findIndex((item) => item.id === conversationId);
  if (index === -1) {
    throw apiError(API_ERROR_CODES.notFound, 'Không tìm thấy cuộc trò chuyện này.');
  }

  conversations.splice(index, 1);
  messagesByConversation.delete(conversationId);
}

/* ------------------------------------------------------------------ */
/* Messages                                                            */
/* ------------------------------------------------------------------ */

export async function mockGetMessages(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ChatMessage[]> {
  await delay(randomBetween(250, 600), signal);

  const exists = conversations.some((item) => item.id === conversationId);
  if (!exists) {
    throw apiError(API_ERROR_CODES.notFound, 'Không tìm thấy cuộc trò chuyện này.');
  }

  return (messagesByConversation.get(conversationId) ?? []).map((message) => ({ ...message }));
}

/** Ghi tin nhắn người dùng vào store và cập nhật preview hội thoại. */
export async function mockAppendUserMessage(
  conversationId: string,
  content: string,
  attachments: ChatAttachment[] = [],
  signal?: AbortSignal,
): Promise<ChatMessage> {
  await delay(randomBetween(120, 260), signal);

  const message: ChatMessage = {
    id: createId('msg'),
    conversationId,
    role: 'user',
    content,
    status: 'completed',
    createdAt: nowIso(),
    ...(attachments.length ? { attachments } : {}),
  };

  const list = messagesByConversation.get(conversationId) ?? [];
  list.push(message);
  messagesByConversation.set(conversationId, list);

  const index = conversations.findIndex((item) => item.id === conversationId);
  if (index !== -1) {
    conversations[index] = {
      ...conversations[index],
      updatedAt: message.createdAt,
      preview: content.slice(0, 90),
      // Hội thoại mới: lấy câu hỏi đầu tiên làm tiêu đề.
      title:
        list.filter((m) => m.role === 'user').length === 1 &&
        conversations[index].title === 'Cuộc trò chuyện mới'
          ? content.slice(0, 48) + (content.length > 48 ? '…' : '')
          : conversations[index].title,
    };
  }

  return { ...message };
}

/** Ghi tin nhắn AI hoàn chỉnh vào store (gọi khi stream kết thúc). */
export function mockCommitAssistantMessage(message: ChatMessage): void {
  const list = messagesByConversation.get(message.conversationId) ?? [];
  const existing = list.findIndex((item) => item.id === message.id);

  if (existing === -1) {
    list.push({ ...message });
  } else {
    list[existing] = { ...message };
  }

  messagesByConversation.set(message.conversationId, list);

  const index = conversations.findIndex((item) => item.id === message.conversationId);
  if (index !== -1) {
    conversations[index] = { ...conversations[index], updatedAt: nowIso() };
  }
}

/* ------------------------------------------------------------------ */
/* Bộ sinh câu trả lời                                                 */
/* ------------------------------------------------------------------ */

interface GeneratedResponse {
  content: string;
  blocks: MessageBlock[];
  sources?: ChatMessage['sources'];
  suggestions?: ChatSuggestion[];
  /** Phase phù hợp với loại câu hỏi. */
  phases: AIProcessingPhase[];
  /** Dấu vết phối hợp của hệ multi-agent. */
  trace?: AgentTrace;
}

/** Đọc số tiền từ câu hỏi: "2 tỷ", "1,5 tỷ", "800 triệu". */
function parseAmount(normalized: string): number | null {
  const billion = normalized.match(/([\d]+(?:[.,]\d+)?)\s*ty/);
  if (billion) {
    return Math.round(parseFloat(billion[1].replace(',', '.')) * 1_000_000_000);
  }
  const million = normalized.match(/([\d]+(?:[.,]\d+)?)\s*trieu/);
  if (million) {
    return Math.round(parseFloat(million[1].replace(',', '.')) * 1_000_000);
  }
  return null;
}

/** Đọc thời hạn từ câu hỏi: "20 năm". */
function parseTermYears(normalized: string): number | null {
  const match = normalized.match(/(\d+)\s*nam/);
  return match ? parseInt(match[1], 10) : null;
}

const LOAN_DISCLAIMER =
  'Kết quả trên chỉ mang tính minh hoạ. Hạn mức, lãi suất và điều kiện thực tế phụ thuộc hồ sơ, kết quả thẩm định và chính sách SHB tại từng thời kỳ.';

function buildLoanResponse(normalized: string): GeneratedResponse {
  const amount = parseAmount(normalized) ?? 2_000_000_000;
  const termYears = parseTermYears(normalized) ?? 20;
  const rate = 9;

  const result = calculateAnnuityLoan({ amount, termYears, annualRatePercent: rate });

  const content = `Tôi có thể giúp bạn ước tính khoản thanh toán. Kết quả dưới đây chỉ mang tính tham khảo và được tính theo mức lãi suất giả định.

Với khoản vay ${formatCurrency(amount)} trong ${termYears} năm ở mức lãi suất giả định ${rate}%/năm, khoản trả hàng tháng ước tính khoảng ${formatCurrency(result.monthlyPayment)} theo phương thức trả đều.

${LOAN_DISCLAIMER}`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content:
          'Tôi có thể giúp bạn ước tính khoản thanh toán. Kết quả dưới đây chỉ mang tính tham khảo và được tính theo mức lãi suất giả định.',
      },
      {
        type: 'loanEstimate',
        amount,
        termYears,
        assumedRatePercent: rate,
        method: 'Trả đều hàng tháng',
        monthlyPayment: result.monthlyPayment,
        totalInterest: result.totalInterest,
        totalPayment: result.totalPayment,
      },
      {
        type: 'table',
        title: 'Thông tin khoản vay',
        columns: [
          { key: 'item', title: 'Hạng mục', align: 'left' },
          { key: 'value', title: 'Giá trị', align: 'right' },
        ],
        rows: [
          { item: 'Số tiền vay', value: formatCurrency(amount) },
          { item: 'Thời hạn', value: `${termYears} năm (${result.months} kỳ)` },
          { item: 'Lãi suất giả định', value: `${rate}%/năm` },
          { item: 'Phương thức', value: 'Dư nợ giảm dần hoặc trả đều' },
          { item: 'Khoản trả ước tính', value: `${formatCurrency(result.monthlyPayment)}/tháng` },
        ],
        footnote: 'Dữ liệu minh hoạ, không phải báo giá tín dụng chính thức của SHB.',
      },
      {
        type: 'chart',
        chartType: 'column',
        title: 'Cơ cấu khoản trả dự kiến',
        description: `So sánh phần gốc, phần lãi và tổng số tiền dự kiến phải trả trong ${termYears} năm.`,
        valueFormat: 'currency',
        data: [
          { category: 'Tiền gốc', value: Math.round(amount) },
          { category: 'Tiền lãi', value: Math.round(result.totalInterest) },
          { category: 'Tổng dự kiến', value: Math.round(result.totalPayment) },
        ],
        yLabel: 'VNĐ',
      },
      {
        type: 'markdown',
        content: `### Các yếu tố có thể làm thay đổi kết quả

- **Lãi suất áp dụng** và **thời gian ưu đãi**.
- **Thu nhập** và khả năng chứng minh nguồn trả nợ.
- **Giá trị tài sản bảo đảm**.
- **Phương thức trả nợ** — trả đều hoặc dư nợ giảm dần.
- **Các khoản phí liên quan** và **kết quả thẩm định**.`,
      },
      {
        type: 'cta',
        actions: [
          {
            id: 'cta-adjust',
            label: 'Điều chỉnh thông số',
            primary: true,
            prompt: 'Tôi muốn điều chỉnh số tiền vay và thời hạn để xem lại ước tính.',
          },
          {
            id: 'cta-product',
            label: 'Xem sản phẩm vay mua nhà',
            prompt: 'Cho tôi biết thêm về sản phẩm vay mua nhà của SHB.',
          },
          {
            id: 'cta-advisor',
            label: 'Đăng ký nhận tư vấn',
            prompt: 'Tôi muốn đăng ký nhận tư vấn từ chuyên viên SHB.',
          },
        ],
      },
      { type: 'disclaimer', content: LOAN_DISCLAIMER },
    ],
    sources: MOCK_LOAN_SOURCES.slice(0, 3),
    suggestions: MOCK_LOAN_SUGGESTIONS,
  };
}

function buildSavingsResponse(): GeneratedResponse {
  const content = `Lãi suất tiền gửi tại SHB được công bố theo từng kỳ hạn và có thể thay đổi theo từng thời kỳ.

Tiền lãi của khoản tiền gửi có kỳ hạn thường được tính theo công thức: Tiền lãi = Số tiền gửi × Lãi suất năm × Số ngày gửi / 365.

Thông tin do SH-AI cung cấp mang tính tham khảo và không thay thế biểu lãi suất chính thức của SHB.`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Lãi suất tiền gửi tại SHB được công bố theo **từng kỳ hạn** và có thể thay đổi theo từng thời kỳ.

### Cách tiền lãi được tính

Với tiền gửi có kỳ hạn, tiền lãi thường được tính theo công thức:

\`\`\`
Tiền lãi = Số tiền gửi × Lãi suất năm × Số ngày gửi / 365
\`\`\`

### Các kỳ hạn phổ biến

- **Ngắn hạn** — 1, 3, 6 tháng: linh hoạt, phù hợp tiền nhàn rỗi.
- **Trung hạn** — 12 tháng: cân bằng giữa lãi suất và tính linh hoạt.
- **Dài hạn** — trên 12 tháng: thường có mức lãi suất cao hơn.`,
      },
      {
        type: 'table',
        title: 'So sánh nhóm kỳ hạn',
        columns: [
          { key: 'term', title: 'Nhóm kỳ hạn', align: 'left' },
          { key: 'rate', title: 'Mức lãi suất', align: 'left' },
          { key: 'flex', title: 'Tính linh hoạt', align: 'left' },
        ],
        rows: [
          { term: '1 – 3 tháng', rate: 'Thấp hơn', flex: 'Rất cao' },
          { term: '6 tháng', rate: 'Trung bình', flex: 'Cao' },
          { term: '12 tháng trở lên', rate: 'Cao hơn', flex: 'Thấp hơn' },
        ],
        footnote:
          'Bảng mang tính minh hoạ. Mức lãi suất cụ thể được SHB công bố chính thức theo từng thời kỳ.',
      },
      {
        type: 'disclaimer',
        content:
          'Thông tin do SH-AI cung cấp mang tính tham khảo và không thay thế biểu lãi suất chính thức của SHB.',
      },
    ],
    sources: [
      {
        id: 'src-savings-rate',
        title: 'Biểu lãi suất tiền gửi',
        type: 'fee',
        excerpt:
          'Biểu lãi suất huy động áp dụng cho khách hàng cá nhân theo từng kỳ hạn, được công bố theo từng thời kỳ.',
        updatedAt: '2026-07-12T00:00:00.000Z',
      },
      {
        id: 'src-savings-product',
        title: 'Sản phẩm tiền gửi có kỳ hạn',
        type: 'product',
        excerpt:
          'Sản phẩm tiền gửi tiết kiệm có kỳ hạn dành cho khách hàng cá nhân với nhiều lựa chọn kỳ hạn khác nhau.',
        updatedAt: '2026-06-05T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-compare-terms',
        label: 'So sánh thêm các kỳ hạn',
        prompt: 'So sánh chi tiết hơn các kỳ hạn tiền gửi tại SHB.',
      },
      {
        id: 'sug-calc-interest',
        label: 'Tính số tiền nhận được',
        prompt: 'Nếu tôi gửi 500 triệu kỳ hạn 12 tháng thì tiền lãi được tính thế nào?',
      },
      {
        id: 'sug-conditions',
        label: 'Xem điều kiện áp dụng',
        prompt: 'Điều kiện áp dụng cho tiền gửi có kỳ hạn là gì?',
      },
    ],
  };
}

function buildCardResponse(): GeneratedResponse {
  const content = `Để chọn thẻ phù hợp, bạn nên cân nhắc theo nhóm chi tiêu chính, phạm vi sử dụng, phí thường niên và hạn mức mong muốn.

Không cung cấp số thẻ đầy đủ, mã CVV hoặc mã OTP cho bất kỳ ai, kể cả người tự xưng là nhân viên ngân hàng.`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Để chọn thẻ phù hợp, bạn nên cân nhắc theo bốn tiêu chí sau:

1. **Nhóm chi tiêu chính** — mua sắm, du lịch, ăn uống hay chi tiêu hàng ngày.
2. **Phạm vi sử dụng** — trong nước hay cần thanh toán quốc tế.
3. **Phí thường niên** — cân đối với mức chi tiêu thực tế mỗi năm.
4. **Hạn mức tín dụng** — phụ thuộc hồ sơ và kết quả thẩm định.`,
      },
      {
        type: 'product',
        title: 'Thẻ tín dụng quốc tế SHB',
        description:
          'Phù hợp với khách hàng có nhu cầu mua sắm trực tuyến và thanh toán khi đi nước ngoài.',
        badge: 'Khách hàng cá nhân',
        benefits: [
          'Thanh toán trong nước và quốc tế',
          'Nhiều hạng thẻ theo nhu cầu chi tiêu',
          'Quản lý giao dịch trên ngân hàng số SHB SAHA',
        ],
        primaryActionLabel: 'Xem các dòng thẻ',
        secondaryActionLabel: 'Điều kiện mở thẻ',
      },
      {
        type: 'alert',
        variant: 'warning',
        title: 'Lưu ý an toàn khi dùng thẻ',
        content:
          'Không cung cấp số thẻ đầy đủ, mã CVV hoặc mã OTP cho bất kỳ ai, kể cả người tự xưng là nhân viên ngân hàng.',
      },
      {
        type: 'disclaimer',
        content:
          'Đặc điểm và chính sách sản phẩm thẻ có thể thay đổi theo từng thời kỳ. Vui lòng tham khảo thông tin chính thức từ SHB trước khi đăng ký.',
      },
    ],
    sources: [
      {
        id: 'src-card-product-2',
        title: 'Thẻ tín dụng quốc tế SHB',
        type: 'product',
        excerpt:
          'Các dòng thẻ tín dụng quốc tế dành cho khách hàng cá nhân với nhiều hạng thẻ khác nhau.',
        updatedAt: '2026-06-20T00:00:00.000Z',
      },
      {
        id: 'src-card-fee-2',
        title: 'Biểu phí dịch vụ thẻ',
        type: 'fee',
        excerpt: 'Biểu phí thường niên, phí rút tiền mặt và các loại phí liên quan tới thẻ.',
        updatedAt: '2026-07-01T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-card-condition',
        label: 'Xem điều kiện áp dụng',
        prompt: 'Điều kiện mở thẻ tín dụng SHB là gì?',
      },
      {
        id: 'sug-card-advisor',
        label: 'Liên hệ chuyên viên SHB',
        prompt: 'Tôi muốn được chuyên viên SHB tư vấn về thẻ.',
      },
    ],
  };
}

function buildSahaResponse(): GeneratedResponse {
  const content = `SHB SAHA là ứng dụng ngân hàng số của SHB. Bạn có thể tải ứng dụng từ App Store hoặc Google Play, sau đó đăng ký bằng số điện thoại và giấy tờ tuỳ thân.

SH-AI không trực tiếp thực hiện giao dịch trong phiên bản demo này.`;

  return {
    content,
    phases: ['understanding', 'reading', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `**SHB SAHA** là ứng dụng ngân hàng số của SHB, cho phép bạn quản lý tài khoản và sử dụng dịch vụ ngay trên điện thoại.

### Các bước bắt đầu

1. **Tải ứng dụng** — tìm "SHB SAHA" trên App Store hoặc Google Play.
2. **Đăng ký** — sử dụng số điện thoại và giấy tờ tuỳ thân của bạn.
3. **Xác thực** — hoàn tất định danh theo hướng dẫn trong ứng dụng.
4. **Thiết lập bảo mật** — tạo mật khẩu và bật phương thức xác thực sinh trắc học nếu thiết bị hỗ trợ.

### Sau khi đăng ký

- Tra cứu số dư và lịch sử giao dịch.
- Quản lý thẻ và tài khoản.
- Sử dụng các dịch vụ ngân hàng số của SHB.`,
      },
      {
        type: 'alert',
        variant: 'warning',
        title: 'Nguyên tắc bảo mật',
        content:
          'Chỉ tải ứng dụng từ App Store hoặc Google Play chính thức. Không chia sẻ mật khẩu, mã PIN hoặc mã OTP với bất kỳ ai.',
      },
      {
        type: 'disclaimer',
        content: 'SH-AI không trực tiếp thực hiện giao dịch trong phiên bản demo này.',
      },
    ],
    sources: [
      {
        id: 'src-saha-guide',
        title: 'Hướng dẫn sử dụng SHB SAHA',
        type: 'procedure',
        excerpt:
          'Tài liệu hướng dẫn đăng ký, kích hoạt và sử dụng các tính năng cơ bản của ngân hàng số SHB SAHA.',
        updatedAt: '2026-06-18T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-saha-security',
        label: 'Bảo mật tài khoản thế nào?',
        prompt: 'Tôi nên làm gì để bảo vệ tài khoản ngân hàng số của mình?',
      },
      {
        id: 'sug-saha-features',
        label: 'SHB SAHA có tính năng gì?',
        prompt: 'SHB SAHA có những tính năng chính nào?',
      },
    ],
  };
}

function buildExchangeRateResponse(): GeneratedResponse {
  const content = `Tỷ giá ngoại tệ tại SHB được cập nhật liên tục trong ngày và phân biệt giữa giá mua vào và giá bán ra.

Thông tin do SH-AI cung cấp mang tính tham khảo và không thay thế bảng tỷ giá chính thức của SHB.`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Tỷ giá ngoại tệ tại SHB được **cập nhật liên tục trong ngày** và phân biệt rõ giữa giá mua vào và giá bán ra.

### Ba loại tỷ giá cần phân biệt

- **Mua tiền mặt** — ngân hàng mua ngoại tệ tiền mặt từ bạn.
- **Mua chuyển khoản** — áp dụng khi ngoại tệ được chuyển vào tài khoản.
- **Bán ra** — ngân hàng bán ngoại tệ cho bạn.

### Nơi tra cứu chính thức

- Website chính thức của SHB.
- Ứng dụng ngân hàng số **SHB SAHA**.
- Quầy giao dịch tại chi nhánh và phòng giao dịch.`,
      },
      {
        type: 'disclaimer',
        content:
          'Tỷ giá thay đổi liên tục theo thị trường. Vui lòng tham khảo bảng tỷ giá chính thức của SHB tại thời điểm giao dịch.',
      },
    ],
    sources: [
      {
        id: 'src-fx-rate',
        title: 'Bảng tỷ giá ngoại tệ',
        type: 'fee',
        excerpt:
          'Bảng tỷ giá mua vào và bán ra các loại ngoại tệ, được cập nhật theo thời gian trong ngày.',
        updatedAt: '2026-07-17T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-fx-where',
        label: 'Tra cứu ở đâu?',
        prompt: 'Tôi có thể tra cứu tỷ giá SHB ở những kênh nào?',
      },
      {
        id: 'sug-fx-business',
        label: 'Ngoại hối cho doanh nghiệp',
        prompt: 'SHB có giải pháp ngoại hối nào cho doanh nghiệp?',
      },
    ],
  };
}

function buildBranchResponse(): GeneratedResponse {
  const content = `Bạn có thể tìm ATM và chi nhánh SHB qua công cụ tìm điểm giao dịch trên website chính thức, ứng dụng SHB SAHA hoặc tổng đài hỗ trợ.`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Bạn có thể tìm ATM và chi nhánh SHB gần nhất qua các kênh sau:

1. **Website chính thức của SHB** — mục tìm điểm giao dịch, lọc theo tỉnh/thành và quận/huyện.
2. **Ứng dụng SHB SAHA** — tìm điểm giao dịch gần bạn dựa trên vị trí hiện tại.
3. **Tổng đài hỗ trợ khách hàng** — hỗ trợ tra cứu địa chỉ chi nhánh.

> Trước khi tới quầy, bạn nên kiểm tra giờ làm việc của chi nhánh, đặc biệt vào cuối tuần và ngày lễ.`,
      },
      {
        type: 'cta',
        actions: [
          {
            id: 'cta-branch-doc',
            label: 'Cần mang theo giấy tờ gì?',
            primary: true,
            prompt: 'Khi tới chi nhánh SHB giao dịch, tôi cần mang theo giấy tờ gì?',
          },
        ],
      },
    ],
    sources: [
      {
        id: 'src-branch-network',
        title: 'Mạng lưới chi nhánh và ATM',
        type: 'product',
        excerpt:
          'Danh sách các điểm giao dịch, chi nhánh và máy ATM của SHB trên toàn quốc kèm địa chỉ và giờ làm việc.',
        updatedAt: '2026-07-05T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-branch-hours',
        label: 'Giờ làm việc thế nào?',
        prompt: 'Chi nhánh SHB làm việc trong khung giờ nào?',
      },
    ],
  };
}

function buildBusinessResponse(): GeneratedResponse {
  const content = `SHB cung cấp các giải pháp dành cho khách hàng doanh nghiệp gồm quản lý dòng tiền, tín dụng, bảo lãnh, thanh toán quốc tế, tài trợ thương mại và ngoại hối.`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `SHB cung cấp nhiều nhóm giải pháp dành cho **khách hàng doanh nghiệp**:

### Quản lý dòng tiền
- Giải pháp tài khoản doanh nghiệp.
- Dịch vụ thu hộ và chi hộ.
- Ngân hàng số dành cho doanh nghiệp.

### Tài trợ và tín dụng
- Sản phẩm tín dụng doanh nghiệp.
- Bảo lãnh ngân hàng.
- Tài trợ thương mại.

### Giao dịch quốc tế
- Thanh toán quốc tế.
- Dịch vụ ngoại hối.`,
      },
      {
        type: 'disclaimer',
        content:
          'Điều kiện, hạn mức và quy trình cụ thể phụ thuộc vào hồ sơ doanh nghiệp và kết quả thẩm định của SHB.',
      },
    ],
    sources: [
      {
        id: 'src-business-solutions',
        title: 'Giải pháp khách hàng doanh nghiệp',
        type: 'product',
        excerpt:
          'Tổng quan các nhóm sản phẩm và dịch vụ dành cho khách hàng doanh nghiệp tại SHB.',
        updatedAt: '2026-06-30T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-biz-guarantee',
        label: 'Bảo lãnh ngân hàng',
        prompt: 'Điều kiện phát hành thư bảo lãnh của SHB là gì?',
      },
      {
        id: 'sug-biz-intl',
        label: 'Thanh toán quốc tế',
        prompt: 'Quy trình thanh toán quốc tế cho doanh nghiệp tại SHB thế nào?',
      },
    ],
  };
}

function buildDocumentResponse(): GeneratedResponse {
  const content = `Tôi đã nhận tài liệu bạn gửi. Ở phiên bản demo, nội dung phân tích dưới đây là dữ liệu minh hoạ.`;

  return {
    content,
    phases: ['understanding', 'reading', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Tôi đã nhận tài liệu bạn gửi và đọc qua nội dung.

### Tóm tắt sơ bộ

- Tài liệu được nhận diện thành công và sẵn sàng để tra cứu.
- Bạn có thể đặt câu hỏi cụ thể về nội dung bên trong tài liệu.
- Khi trả lời dựa trên tài liệu, tôi sẽ trích dẫn phần nội dung liên quan trong mục **Nguồn tham khảo**.`,
      },
      {
        type: 'alert',
        variant: 'info',
        title: 'Phiên bản demo',
        content:
          'Chức năng đọc và phân tích tài liệu đang ở chế độ mô phỏng. Nội dung phân tích là dữ liệu minh hoạ, không phải kết quả xử lý tài liệu thật.',
      },
    ],
    sources: [
      {
        id: 'src-user-doc',
        title: 'Tài liệu bạn đã tải lên',
        type: 'attachment',
        excerpt:
          'Nội dung được trích từ tài liệu bạn gửi trong cuộc trò chuyện này. Đây là dữ liệu minh hoạ cho phiên bản demo.',
        updatedAt: nowIso(),
      },
    ],
    suggestions: [
      {
        id: 'sug-doc-summary',
        label: 'Tóm tắt tài liệu',
        prompt: 'Hãy tóm tắt các ý chính trong tài liệu tôi vừa gửi.',
      },
    ],
  };
}

/* ------------------------------------------------------------------ */
/* Multi-agent: thẩm định hồ sơ vay                                    */
/* ------------------------------------------------------------------ */

/** Tìm khách hàng được nhắc tới trong câu hỏi. */
function findCustomerInText(normalized: string) {
  return MOCK_CUSTOMERS.find((customer) => {
    const name = normalizeVietnamese(customer.fullName);
    const code = normalizeVietnamese(customer.code);
    return normalized.includes(name) || normalized.includes(code);
  });
}

/**
 * Thẩm định hồ sơ vay bằng hệ multi-agent:
 * Planner phân rã việc -> Credit / Legal / Operations chạy song song -> tổng hợp.
 */
function buildLoanReviewResponse(normalized: string): GeneratedResponse {
  const customer = findCustomerInText(normalized);
  const application =
    (customer && findLoanByCustomer(customer.id)) ??
    MOCK_LOAN_APPLICATIONS.find((item) => normalized.includes(normalizeVietnamese(item.code))) ??
    MOCK_LOAN_APPLICATIONS[0];

  const failed = application.checks.filter((check) => !check.passed);
  const recommendation =
    failed.length === 0
      ? 'Đề xuất: **đủ điều kiện phê duyệt** theo chính sách hiện hành.'
      : `Đề xuất: **chưa đủ điều kiện phê duyệt** — có ${failed.length} chốt kiểm tra không đạt.`;

  const trace: AgentTrace = {
    summary: `Điều phối 4 chuyên gia số thẩm định hồ sơ ${application.code}`,
    steps: [
      {
        id: 'step-plan',
        agent: 'planner',
        title: 'Phân rã yêu cầu thẩm định',
        description:
          'Xác định hồ sơ cần thẩm định, chia thành 3 nhánh song song: năng lực tín dụng, pháp lý & tuân thủ, tính đầy đủ hồ sơ.',
        status: 'success',
        tool: {
          name: 'get_loan_application',
          label: 'Truy vấn hồ sơ vay',
          result: `${application.code} — ${formatCurrency(application.amount)}`,
        },
        durationMs: 420,
      },
      {
        id: 'step-credit',
        agent: 'credit',
        title: 'Thẩm định năng lực trả nợ',
        description: application.checks
          .filter((check) => check.agent === 'credit')
          .map((check) => `${check.passed ? 'Đạt' : 'Không đạt'} — ${check.label}`)
          .join('. '),
        status: application.checks.some((c) => c.agent === 'credit' && !c.passed) ? 'error' : 'success',
        tool: {
          name: 'query_credit_bureau',
          label: 'Tra cứu lịch sử tín dụng',
          result: customer ? `Điểm ${customer.creditScore}, DTI ${customer.dti}%` : 'Đã lấy dữ liệu',
        },
        durationMs: 1_180,
      },
      {
        id: 'step-legal',
        agent: 'legal',
        title: 'Kiểm tra pháp lý và tuân thủ',
        description: application.checks
          .filter((check) => check.agent === 'legal')
          .map((check) => `${check.passed ? 'Đạt' : 'Không đạt'} — ${check.label}`)
          .join('. '),
        status: application.checks.some((c) => c.agent === 'legal' && !c.passed) ? 'error' : 'success',
        tool: {
          name: 'screen_aml_watchlist',
          label: 'Sàng lọc AML/KYC',
          result: 'Không trùng danh sách cảnh báo',
        },
        durationMs: 860,
      },
      {
        id: 'step-product',
        agent: 'product',
        title: 'Đối chiếu điều kiện sản phẩm',
        description:
          application.ltv > 0
            ? `LTV ${application.ltv}% so với ngưỡng 70% của sản phẩm. Kỳ hạn ${application.termYears} năm.`
            : `Sản phẩm tín chấp — không có tài sản bảo đảm. Kỳ hạn ${application.termYears} năm.`,
        status: application.ltv > 70 ? 'error' : 'success',
        tool: {
          name: 'match_product_policy',
          label: 'Đối chiếu điều kiện sản phẩm',
          result: application.ltv > 0 ? `LTV ${application.ltv}% ≤ 70% — hợp lệ` : 'Tín chấp',
        },
        durationMs: 540,
      },
      {
        id: 'step-ops',
        agent: 'operations',
        title: 'Đối chiếu tính đầy đủ hồ sơ',
        description: application.checks
          .filter((check) => check.agent === 'operations')
          .map((check) => `${check.passed ? 'Đạt' : 'Không đạt'} — ${check.label}`)
          .join('. '),
        status: application.checks.some((c) => c.agent === 'operations' && !c.passed)
          ? 'error'
          : 'success',
        tool: {
          name: 'check_document_checklist',
          label: 'Đối chiếu danh mục chứng từ',
          result: `${application.checks.filter((c) => c.agent === 'operations' && c.passed).length} mục đạt`,
        },
        durationMs: 640,
      },
      {
        id: 'step-merge',
        agent: 'planner',
        title: 'Tổng hợp kết luận và trình chuyên viên',
        description:
          'Hợp nhất kết quả 3 nhánh, đối chiếu hạn mức phê duyệt và chuẩn bị đề xuất quyết định.',
        status: 'success',
        durationMs: 380,
      },
    ],
  };

  const content = `Đã hoàn tất thẩm định hồ sơ ${application.code} của ${application.customerName}.

${application.checks.length - failed.length}/${application.checks.length} chốt kiểm tra đạt. ${recommendation.replace(/\*\*/g, '')}

Quyết định cuối cùng thuộc thẩm quyền của chuyên viên. SH-AI không tự phê duyệt khoản vay.`;

  return {
    content,
    phases: ['understanding', 'searching', 'reading', 'composing'],
    trace,
    blocks: [
      {
        type: 'markdown',
        content: `Đã hoàn tất thẩm định hồ sơ **${application.code}** của **${application.customerName}**.

${application.checks.length - failed.length}/${application.checks.length} chốt kiểm tra đạt. ${recommendation}`,
      },
      { type: 'loanApproval', application },
      ...(customer ? [{ type: 'customerSummary' as const, customer }] : []),
      {
        type: 'alert',
        variant: failed.length === 0 ? 'info' : 'warning',
        title: 'Thẩm quyền quyết định',
        content:
          'Kết quả trên là đề xuất của hệ chuyên gia số dựa trên chính sách và dữ liệu hiện có. Quyết định phê duyệt thuộc về chuyên viên và được ghi vết kiểm toán.',
      },
      {
        type: 'disclaimer',
        content:
          'Dữ liệu hồ sơ trong bản demo là hư cấu. Hệ thống không kết nối tới core banking và không tạo ra quyết định tín dụng thật.',
      },
    ],
    sources: [
      {
        id: 'src-credit-policy',
        title: 'Chính sách cấp tín dụng khách hàng cá nhân',
        type: 'policy',
        excerpt:
          'Quy định ngưỡng DTI tối đa 50%, điểm tín dụng tối thiểu theo từng sản phẩm và yêu cầu chứng minh thu nhập.',
        updatedAt: '2026-05-15T00:00:00.000Z',
      },
      {
        id: 'src-approval-authority',
        title: 'Phân cấp thẩm quyền phê duyệt',
        type: 'procedure',
        excerpt:
          'Quy định hạn mức phê duyệt theo từng cấp chuyên viên và điều kiện trình cấp cao hơn.',
        updatedAt: '2026-06-01T00:00:00.000Z',
      },
    ],
    suggestions: [
      {
        id: 'sug-why-fail',
        label: 'Vì sao chốt kiểm tra không đạt?',
        prompt: `Giải thích chi tiết các chốt kiểm tra không đạt của hồ sơ ${application.code}.`,
      },
      {
        id: 'sug-similar',
        label: 'Tiền lệ hồ sơ tương tự',
        prompt: `Có hồ sơ nào tương tự ${application.code} đã được xử lý chưa?`,
      },
      {
        id: 'sug-checklist',
        label: 'Chứng từ còn thiếu',
        prompt: `Hồ sơ ${application.code} còn thiếu chứng từ gì?`,
      },
    ],
  };
}

/** Tra cứu nhanh hồ sơ một khách hàng. */
function buildCustomerLookupResponse(normalized: string): GeneratedResponse {
  const customer = findCustomerInText(normalized) ?? MOCK_CUSTOMERS[0];
  const loan = findLoanByCustomer(customer.id);

  const trace: AgentTrace = {
    summary: `Tra cứu hồ sơ khách hàng ${customer.code}`,
    steps: [
      {
        id: 'step-plan-cus',
        agent: 'planner',
        title: 'Xác định phạm vi tra cứu',
        description: 'Cần thông tin định danh, hồ sơ tín dụng và các hồ sơ vay đang mở.',
        status: 'success',
        durationMs: 260,
      },
      {
        id: 'step-cus-fetch',
        agent: 'operations',
        title: 'Truy xuất hồ sơ khách hàng',
        status: 'success',
        tool: {
          name: 'get_customer_profile',
          label: 'Truy vấn CIF',
          result: `${customer.code} — ${customer.branch}`,
        },
        durationMs: 520,
      },
      {
        id: 'step-cus-credit',
        agent: 'credit',
        title: 'Đánh giá nhanh hồ sơ tín dụng',
        description: `Điểm tín dụng ${customer.creditScore}, DTI ${customer.dti}%, dư nợ ${formatCurrency(customer.existingDebt)}.`,
        status: 'success',
        durationMs: 610,
      },
    ],
  };

  const content = `Hồ sơ khách hàng ${customer.fullName} (${customer.code}).

Điểm tín dụng ${customer.creditScore}, DTI ${customer.dti}%, dư nợ hiện tại ${formatCurrency(customer.existingDebt)}. Chi nhánh quản lý: ${customer.branch}.

Thông tin định danh được hiển thị ở dạng che theo nguyên tắc tối thiểu hoá dữ liệu.`;

  return {
    content,
    phases: ['understanding', 'searching', 'composing'],
    trace,
    blocks: [
      {
        type: 'markdown',
        content: `Hồ sơ khách hàng **${customer.fullName}** (${customer.code}).`,
      },
      { type: 'customerSummary', customer },
      ...(loan
        ? [
            {
              type: 'markdown' as const,
              content: `Khách hàng đang có **1 hồ sơ vay chờ xử lý**: ${loan.code} — ${formatCurrency(loan.amount)} (${loan.productName}).`,
            },
          ]
        : []),
      {
        type: 'alert',
        variant: 'info',
        title: 'Bảo vệ dữ liệu khách hàng',
        content:
          'Thông tin định danh được che mặc định. Việc xem dữ liệu đầy đủ cần quyền riêng và được ghi vết kiểm toán.',
      },
    ],
    sources: [
      {
        id: 'src-cif',
        title: 'Hồ sơ khách hàng (CIF)',
        type: 'attachment',
        excerpt: `Dữ liệu định danh và quan hệ tín dụng của khách hàng ${customer.code}.`,
        updatedAt: nowIso(),
      },
    ],
    suggestions: loan
      ? [
          {
            id: 'sug-review-loan',
            label: `Thẩm định hồ sơ ${loan.code}`,
            prompt: `Thẩm định hồ sơ vay ${loan.code} của ${customer.fullName}.`,
          },
        ]
      : [
          {
            id: 'sug-history',
            label: 'Lịch sử giao dịch',
            prompt: `Lịch sử quan hệ tín dụng của ${customer.fullName} thế nào?`,
          },
        ],
  };
}

function buildGenericResponse(): GeneratedResponse {
  const content = `Tôi là SH-AI, trợ lý tài chính của SHB. Tôi có thể hỗ trợ bạn tra cứu sản phẩm, lãi suất, tỷ giá, tư vấn thẻ và khoản vay, cũng như hướng dẫn sử dụng ngân hàng số SHB SAHA.`;

  return {
    content,
    phases: ['understanding', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Tôi là **SH-AI**, trợ lý tài chính của SHB. Tôi có thể đồng hành cùng bạn ở những nội dung sau:

### Khách hàng cá nhân
- Tra cứu lãi suất tiền gửi và tỷ giá.
- Tư vấn lựa chọn thẻ.
- Ước tính khoản vay mua nhà, mua ô tô, tiêu dùng.
- Hướng dẫn sử dụng ngân hàng số **SHB SAHA**.
- Tìm ATM và chi nhánh.

### Khách hàng doanh nghiệp
- Quản lý dòng tiền và tài khoản doanh nghiệp.
- Tín dụng, bảo lãnh, tài trợ thương mại.
- Thanh toán quốc tế và ngoại hối.

Bạn có thể mô tả nhu cầu cụ thể, hoặc tải lên tài liệu để tôi hỗ trợ tra cứu.`,
      },
    ],
    suggestions: [
      {
        id: 'sug-generic-rate',
        label: 'Tra cứu lãi suất',
        prompt: 'Cho tôi xem các lựa chọn kỳ hạn tiền gửi và cách tính tiền lãi.',
      },
      {
        id: 'sug-generic-loan',
        label: 'Ước tính khoản vay',
        prompt: 'Tôi muốn vay mua nhà. Hãy giúp tôi ước tính khoản thanh toán hàng tháng.',
      },
      {
        id: 'sug-generic-advisor',
        label: 'Liên hệ chuyên viên SHB',
        prompt: 'Tôi muốn được chuyên viên SHB hỗ trợ trực tiếp.',
      },
    ],
  };
}

function buildAdvisorResponse(): GeneratedResponse {
  const content = `Tôi có thể kết nối bạn với chuyên viên SHB. Ở phiên bản demo, thao tác này chỉ mang tính minh hoạ và chưa gửi yêu cầu thật.`;

  return {
    content,
    phases: ['understanding', 'composing'],
    blocks: [
      {
        type: 'markdown',
        content: `Tôi có thể kết nối bạn với **chuyên viên SHB** để được tư vấn chi tiết hơn.

Khi chuyển tiếp, chuyên viên sẽ hỗ trợ bạn:

- Tư vấn sản phẩm phù hợp với hồ sơ thực tế.
- Giải thích điều kiện và quy trình cụ thể.
- Hướng dẫn chuẩn bị hồ sơ.`,
      },
      {
        type: 'alert',
        variant: 'info',
        title: 'Phiên bản demo',
        content:
          'Yêu cầu kết nối chuyên viên chưa được gửi đi trong bản demo này. Vui lòng liên hệ SHB qua kênh chính thức để được hỗ trợ.',
      },
    ],
    suggestions: [
      {
        id: 'sug-advisor-back',
        label: 'Quay lại tư vấn với SH-AI',
        prompt: 'Tôi muốn tiếp tục trao đổi với SH-AI.',
      },
    ],
  };
}

/** Chọn câu trả lời dựa trên nội dung câu hỏi. */
function generateResponse(userContent: string, mode: ChatMode, hasAttachment: boolean): GeneratedResponse {
  const normalized = normalizeVietnamese(userContent);

  if (hasAttachment || mode === 'document') return buildDocumentResponse();

  // Chế độ nghiệp vụ do chuyên viên chọn -> ưu tiên agent tương ứng.
  if (mode === 'credit' && !/(khach hang|cif)/.test(normalized)) {
    return buildLoanReviewResponse(normalized);
  }

  // Nghiệp vụ nội bộ: thẩm định / phê duyệt hồ sơ vay (ưu tiên cao nhất).
  if (/(tham dinh|phe duyet|ho so vay|hs 2026|duyet ho so|xet duyet|ho so cho duyet)/.test(normalized)) {
    return buildLoanReviewResponse(normalized);
  }
  // Tra cứu khách hàng theo tên hoặc mã CIF.
  if (/(khach hang|cif|ho so khach|thong tin khach)/.test(normalized) || findCustomerInText(normalized)) {
    return buildCustomerLookupResponse(normalized);
  }

  if (/(chuyen vien|tu van truc tiep|nhan vien ho tro|dang ky nhan tu van)/.test(normalized)) {
    return buildAdvisorResponse();
  }
  if (/(vay|tra gop|khoan vay|mua nha|mua o to|mua oto)/.test(normalized)) {
    return buildLoanResponse(normalized);
  }
  if (/(lai suat|tiet kiem|tien gui|ky han)/.test(normalized)) {
    return buildSavingsResponse();
  }
  if (/(the tin dung|the ghi no|chon the|tu van the|the shb)/.test(normalized)) {
    return buildCardResponse();
  }
  if (/(saha|ngan hang so|ung dung|mobile banking)/.test(normalized)) {
    return buildSahaResponse();
  }
  if (/(ty gia|ngoai te|usd|eur|ngoai hoi)/.test(normalized)) {
    return buildExchangeRateResponse();
  }
  if (/(atm|chi nhanh|phong giao dich|diem giao dich)/.test(normalized)) {
    return buildBranchResponse();
  }
  if (/(doanh nghiep|bao lanh|thanh toan quoc te|dong tien|tai tro thuong mai)/.test(normalized)) {
    return buildBusinessResponse();
  }

  return buildGenericResponse();
}

/* ------------------------------------------------------------------ */
/* Streaming                                                           */
/* ------------------------------------------------------------------ */

/**
 * Mô phỏng streaming câu trả lời của AI.
 *
 * Backend thật có thể thay thế bằng SSE / WebSocket / chunked HTTP mà không
 * đổi hình dạng sự kiện (`StreamEvent`), nên UI không cần sửa.
 *
 * Hỗ trợ huỷ qua `AbortSignal` — dùng cho nút "Dừng tạo câu trả lời" và
 * cleanup khi component unmount.
 */
export async function* mockStreamAssistantResponse(
  conversationId: string,
  userContent: string,
  options: { mode?: ChatMode; hasAttachment?: boolean; signal?: AbortSignal } = {},
): AsyncGenerator<StreamEvent> {
  const { mode = 'general', hasAttachment = false, signal } = options;

  const triggeredError = detectErrorTrigger(userContent);
  if (triggeredError) {
    yield { type: 'phase', phase: 'connecting' };
    await delay(randomBetween(400, 700), signal);
    yield { type: 'error', error: triggeredError };
    return;
  }

  const response = generateResponse(userContent, mode, hasAttachment);
  const messageId = createId('msg');
  const createdAt = nowIso();

  // 1. Các phase xử lý cấp cao (an toàn, không lộ chain-of-thought nội bộ).
  yield { type: 'phase', phase: 'connecting' };
  await delay(randomBetween(200, 350), signal);

  for (const phase of response.phases) {
    yield { type: 'phase', phase };
    await delay(randomBetween(500, 1_200), signal);
  }

  // 2. Streaming nội dung theo từng chunk từ.
  const words = response.content.split(/(\s+)/);
  let streamed = '';

  for (let i = 0; i < words.length; i += 2) {
    const chunk = words[i] + (words[i + 1] ?? '');
    streamed += chunk;
    yield { type: 'delta', text: chunk };
    await delay(randomBetween(30, 80), signal);
  }

  // 3. Hoàn tất — trả về message đầy đủ kèm rich blocks.
  const message: ChatMessage = {
    id: messageId,
    conversationId,
    role: 'assistant',
    content: response.content,
    status: 'completed',
    createdAt,
    blocks: response.blocks,
    ...(response.sources ? { sources: response.sources } : {}),
    ...(response.suggestions ? { suggestions: response.suggestions } : {}),
    ...(response.trace ? { trace: response.trace } : {}),
  };

  mockCommitAssistantMessage(message);
  yield { type: 'complete', message };
}

/* ------------------------------------------------------------------ */
/* Attachments                                                         */
/* ------------------------------------------------------------------ */

/** Kiểm tra file trước khi upload. Trả về thông báo lỗi hoặc null nếu hợp lệ. */
export function validateAttachment(file: File, existingNames: string[] = []): string | null {
  if (!ACCEPTED_MIME_TYPES[file.type]) {
    return 'Định dạng không được hỗ trợ. Chấp nhận PDF, DOCX, XLSX, PNG, JPG.';
  }
  if (file.size > ATTACHMENT_LIMITS.maxSizeBytes) {
    return 'Dung lượng vượt quá 10 MB.';
  }
  if (file.name.length > ATTACHMENT_LIMITS.maxNameLength) {
    return 'Tên file quá dài.';
  }
  if (existingNames.includes(file.name)) {
    return 'File này đã được đính kèm.';
  }
  return null;
}

/**
 * Mô phỏng upload file. KHÔNG gửi nội dung file đi đâu cả.
 * `onProgress` cho phép UI hiển thị tiến trình thật của mô phỏng.
 */
export async function mockUploadAttachment(
  file: File,
  options: { onProgress?: (percent: number) => void; signal?: AbortSignal } = {},
): Promise<ChatAttachment> {
  const { onProgress, signal } = options;

  const validationError = validateAttachment(file);
  if (validationError) {
    throw apiError(API_ERROR_CODES.validation, validationError);
  }

  // File tên chứa "loi" -> mô phỏng upload thất bại (phục vụ demo error state).
  const shouldFail = normalizeVietnamese(file.name).includes('loi');

  const totalDuration = randomBetween(600, 1_400);
  const steps = 10;

  for (let step = 1; step <= steps; step += 1) {
    await delay(totalDuration / steps, signal);
    onProgress?.(Math.round((step / steps) * 100));
  }

  if (shouldFail) {
    throw apiError(API_ERROR_CODES.uploadFailed, 'Tải tài liệu thất bại. Vui lòng thử lại.');
  }

  return {
    id: createId('att'),
    name: file.name,
    mimeType: file.type,
    size: file.size,
    status: 'done',
    progress: 100,
  };
}
