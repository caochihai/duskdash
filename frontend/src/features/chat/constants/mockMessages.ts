import type { ChatMessage, ChatSuggestion, MessageBlock } from '@/types/chat';
import type { AgentTrace } from '@/types/agent';
import type { ChatSource } from '@/types/source';
import { formatCurrency } from '@/utils/formatCurrency';
import { DEMO_LOAN_CONVERSATION_ID } from './mockConversations';
import { MOCK_CUSTOMERS, MOCK_LOAN_APPLICATIONS } from './mockCustomers';

/* ------------------------------------------------------------------ */
/* Nguồn tham khảo mock — tài liệu NỘI BỘ của ngân hàng                */
/* ------------------------------------------------------------------ */

export const MOCK_LOAN_SOURCES: ChatSource[] = [
  {
    id: 'src-credit-policy',
    title: 'Chính sách cấp tín dụng khách hàng cá nhân',
    type: 'policy',
    excerpt:
      'Quy định ngưỡng DTI tối đa 50%, LTV tối đa 70% với tài sản bảo đảm là bất động sản, và điểm tín dụng tối thiểu theo từng sản phẩm.',
    updatedAt: '2026-05-15T00:00:00.000Z',
    documentName: 'CS-TD-2026-v3.pdf',
  },
  {
    id: 'src-approval-authority',
    title: 'Phân cấp thẩm quyền phê duyệt',
    type: 'procedure',
    excerpt:
      'Chuyên viên tín dụng được phê duyệt tới 3 tỷ đồng. Khoản vay vượt hạn mức phải trình Hội đồng tín dụng chi nhánh.',
    updatedAt: '2026-06-01T00:00:00.000Z',
    documentName: 'QD-PC-2026.pdf',
  },
  {
    id: 'src-collateral-rule',
    title: 'Quy định về tài sản bảo đảm',
    type: 'policy',
    excerpt:
      'Yêu cầu định giá độc lập, kiểm tra tình trạng pháp lý và xác nhận không trùng thế chấp trước khi giải ngân.',
    updatedAt: '2026-04-20T00:00:00.000Z',
    documentName: 'QD-TSBD-2026.pdf',
  },
  {
    id: 'src-aml-procedure',
    title: 'Quy trình sàng lọc AML/KYC',
    type: 'procedure',
    excerpt:
      'Đối chiếu danh sách cảnh báo trong nước và quốc tế, xác thực hồ sơ định danh còn hiệu lực trước khi cấp tín dụng.',
    updatedAt: '2026-03-11T00:00:00.000Z',
    documentName: 'QT-AML-2026.pdf',
  },
];

/* ------------------------------------------------------------------ */
/* Kịch bản demo: thẩm định hồ sơ HS-2026-0481                         */
/* ------------------------------------------------------------------ */

const demoApplication = MOCK_LOAN_APPLICATIONS[0];
const demoCustomer = MOCK_CUSTOMERS[0];

/**
 * Agent trace của kịch bản demo.
 * Thể hiện Planner phân rã việc -> 4 chuyên gia số chạy -> tổng hợp kết luận.
 */
const demoTrace: AgentTrace = {
  summary: `Điều phối 4 chuyên gia số thẩm định hồ sơ ${demoApplication.code}`,
  steps: [
    {
      id: 'demo-plan',
      agent: 'planner',
      title: 'Phân rã yêu cầu thẩm định',
      description:
        'Xác định hồ sơ cần thẩm định và chia thành 4 nhánh: năng lực tín dụng, pháp lý & tuân thủ, đối chiếu sản phẩm, tính đầy đủ hồ sơ.',
      status: 'success',
      tool: {
        name: 'get_loan_application',
        label: 'Truy vấn hồ sơ vay',
        result: `${demoApplication.code} — ${formatCurrency(demoApplication.amount)}`,
      },
      durationMs: 420,
    },
    {
      id: 'demo-credit',
      agent: 'credit',
      title: 'Thẩm định năng lực trả nợ',
      description:
        'DTI 31% — dưới ngưỡng chính sách 50%. Điểm tín dụng 742, không phát sinh nợ quá hạn trong 24 tháng.',
      status: 'success',
      tool: {
        name: 'query_credit_bureau',
        label: 'Tra cứu lịch sử tín dụng',
        result: 'Điểm 742, DTI 31%, không nợ xấu',
      },
      durationMs: 1_180,
    },
    {
      id: 'demo-legal',
      agent: 'legal',
      title: 'Kiểm tra pháp lý và tuân thủ',
      description:
        'Sổ hồng hợp lệ, không tranh chấp, không trùng thế chấp. Không trùng danh sách cảnh báo AML.',
      status: 'success',
      tool: {
        name: 'screen_aml_watchlist',
        label: 'Sàng lọc AML/KYC',
        result: 'Không trùng danh sách cảnh báo',
      },
      durationMs: 860,
    },
    {
      id: 'demo-product',
      agent: 'product',
      title: 'Đối chiếu điều kiện sản phẩm',
      description:
        'LTV 65% nằm trong ngưỡng 70% của sản phẩm vay mua nhà. Kỳ hạn 20 năm hợp lệ.',
      status: 'success',
      tool: {
        name: 'match_product_policy',
        label: 'Đối chiếu điều kiện sản phẩm',
        result: 'LTV 65% ≤ 70% — hợp lệ',
      },
      durationMs: 540,
    },
    {
      id: 'demo-ops',
      agent: 'operations',
      title: 'Đối chiếu tính đầy đủ hồ sơ',
      description: 'Đủ 8/8 chứng từ bắt buộc theo quy trình cho vay mua nhà.',
      status: 'success',
      tool: {
        name: 'check_document_checklist',
        label: 'Đối chiếu danh mục chứng từ',
        result: '8/8 chứng từ đầy đủ',
      },
      durationMs: 640,
    },
    {
      id: 'demo-merge',
      agent: 'planner',
      title: 'Tổng hợp kết luận và trình chuyên viên',
      description:
        'Hợp nhất kết quả 4 nhánh, đối chiếu hạn mức phê duyệt của chuyên viên và chuẩn bị đề xuất quyết định.',
      status: 'success',
      durationMs: 380,
    },
  ],
};

const DEMO_DISCLAIMER =
  'Dữ liệu hồ sơ trong bản demo là hư cấu. Hệ thống không kết nối tới core banking và không tạo ra quyết định tín dụng thật.';

export const MOCK_LOAN_SUGGESTIONS: ChatSuggestion[] = [
  {
    id: 'sug-why-pass',
    label: 'Căn cứ của từng chốt kiểm tra?',
    prompt: `Giải thích căn cứ chính sách cho từng chốt kiểm tra của hồ sơ ${demoApplication.code}.`,
  },
  {
    id: 'sug-risk',
    label: 'Rủi ro còn lại là gì?',
    prompt: `Hồ sơ ${demoApplication.code} còn rủi ro tiềm ẩn nào cần lưu ý?`,
  },
  {
    id: 'sug-similar',
    label: 'Tiền lệ hồ sơ tương tự',
    prompt: `Có hồ sơ nào tương tự ${demoApplication.code} đã được xử lý chưa?`,
  },
  {
    id: 'sug-customer',
    label: 'Xem hồ sơ khách hàng',
    prompt: `Cho tôi thông tin khách hàng ${demoCustomer.fullName} (${demoCustomer.code}).`,
  },
];

const demoBlocks: MessageBlock[] = [
  {
    type: 'markdown',
    content: `Đã hoàn tất thẩm định hồ sơ **${demoApplication.code}** của **${demoApplication.customerName}**.

**5/5 chốt kiểm tra đạt.** Đề xuất: **đủ điều kiện phê duyệt** theo chính sách hiện hành.`,
  },
  { type: 'loanApproval', application: demoApplication },
  { type: 'customerSummary', customer: demoCustomer },
  {
    type: 'markdown',
    content: `### Cơ sở đề xuất

- **Năng lực trả nợ** — DTI 31%, dưới ngưỡng chính sách 50%.
- **Lịch sử tín dụng** — điểm 742, không phát sinh nợ quá hạn 24 tháng.
- **Tài sản bảo đảm** — LTV 65%, dưới ngưỡng 70% của sản phẩm.
- **Tuân thủ** — không trùng danh sách cảnh báo AML, hồ sơ định danh còn hiệu lực.
- **Hồ sơ** — đủ 8/8 chứng từ bắt buộc.`,
  },
  {
    type: 'chart',
    chartType: 'column',
    title: 'Đối chiếu chỉ số với ngưỡng chính sách',
    description: 'Các chỉ số chính của hồ sơ so với ngưỡng tối đa theo chính sách tín dụng.',
    valueFormat: 'percent',
    data: [
      { category: 'DTI hồ sơ', value: 31 },
      { category: 'DTI ngưỡng', value: 50 },
      { category: 'LTV hồ sơ', value: 65 },
      { category: 'LTV ngưỡng', value: 70 },
    ],
    yLabel: '%',
  },
  {
    type: 'alert',
    variant: 'info',
    title: 'Thẩm quyền quyết định',
    content:
      'Kết quả trên là đề xuất của hệ chuyên gia số dựa trên chính sách và dữ liệu hiện có. Quyết định phê duyệt thuộc về chuyên viên và được ghi vết kiểm toán.',
  },
  { type: 'disclaimer', content: DEMO_DISCLAIMER },
];

/** Text thuần tương ứng — dùng cho streaming và nút "Sao chép". */
const demoPlainText = `Đã hoàn tất thẩm định hồ sơ ${demoApplication.code} của ${demoApplication.customerName}.

5/5 chốt kiểm tra đạt. Đề xuất: đủ điều kiện phê duyệt theo chính sách hiện hành.

Cơ sở đề xuất: DTI 31% dưới ngưỡng 50%; điểm tín dụng 742 không có nợ quá hạn; LTV 65% dưới ngưỡng 70%; không trùng danh sách cảnh báo AML; đủ 8/8 chứng từ bắt buộc.

Quyết định phê duyệt thuộc thẩm quyền của chuyên viên. SH-AI không tự phê duyệt khoản vay.

${DEMO_DISCLAIMER}`;

const nowMinus = (minutes: number) => new Date(Date.now() - minutes * 60 * 1000).toISOString();

export const MOCK_LOAN_MESSAGES: ChatMessage[] = [
  {
    id: 'msg-review-user-1',
    conversationId: DEMO_LOAN_CONVERSATION_ID,
    role: 'user',
    content: `Thẩm định hồ sơ vay ${demoApplication.code} của ${demoApplication.customerName}.`,
    status: 'completed',
    createdAt: nowMinus(64),
  },
  {
    id: 'msg-review-assistant-1',
    conversationId: DEMO_LOAN_CONVERSATION_ID,
    role: 'assistant',
    content: demoPlainText,
    status: 'completed',
    createdAt: nowMinus(63),
    blocks: demoBlocks,
    trace: demoTrace,
    sources: MOCK_LOAN_SOURCES.slice(0, 3),
    suggestions: MOCK_LOAN_SUGGESTIONS,
  },
];

/* ------------------------------------------------------------------ */
/* Hội thoại: kiểm tra tuân thủ                                        */
/* ------------------------------------------------------------------ */

export const MOCK_COMPLIANCE_MESSAGES: ChatMessage[] = [
  {
    id: 'msg-comp-user-1',
    conversationId: 'conv-compliance-check',
    role: 'user',
    content: 'Kiểm tra tuân thủ AML/KYC cho khách hàng Công ty CP Bao bì VinaNova.',
    status: 'completed',
    createdAt: nowMinus(240),
  },
  {
    id: 'msg-comp-assistant-1',
    conversationId: 'conv-compliance-check',
    role: 'assistant',
    content:
      'Đã hoàn tất sàng lọc AML/KYC cho Công ty CP Bao bì VinaNova. Không phát hiện trùng khớp danh sách cảnh báo. Hồ sơ định danh doanh nghiệp còn hiệu lực.',
    status: 'completed',
    createdAt: nowMinus(239),
    trace: {
      summary: 'Pháp chế & Tuân thủ sàng lọc khách hàng doanh nghiệp',
      steps: [
        {
          id: 'comp-plan',
          agent: 'planner',
          title: 'Xác định phạm vi sàng lọc',
          description: 'Cần đối chiếu danh sách cảnh báo, kiểm tra hiệu lực hồ sơ pháp lý.',
          status: 'success',
          durationMs: 280,
        },
        {
          id: 'comp-legal',
          agent: 'legal',
          title: 'Đối chiếu danh sách cảnh báo',
          description: 'Sàng lọc danh sách trong nước và quốc tế với tên doanh nghiệp và người đại diện.',
          status: 'success',
          tool: {
            name: 'screen_aml_watchlist',
            label: 'Sàng lọc AML/KYC',
            result: 'Không có trùng khớp',
          },
          durationMs: 940,
        },
        {
          id: 'comp-ops',
          agent: 'operations',
          title: 'Kiểm tra hiệu lực hồ sơ pháp lý',
          description: 'Giấy phép kinh doanh còn hiệu lực, người đại diện hợp pháp.',
          status: 'success',
          tool: {
            name: 'verify_legal_documents',
            label: 'Xác thực hồ sơ pháp lý',
            result: 'Còn hiệu lực',
          },
          durationMs: 620,
        },
      ],
    },
    blocks: [
      {
        type: 'markdown',
        content: `Đã hoàn tất sàng lọc **AML/KYC** cho **Công ty CP Bao bì VinaNova**.

### Kết quả

- **Danh sách cảnh báo** — không phát hiện trùng khớp (trong nước và quốc tế).
- **Hồ sơ pháp lý** — giấy phép kinh doanh còn hiệu lực.
- **Người đại diện** — hợp pháp, hồ sơ định danh còn hạn.`,
      },
      { type: 'customerSummary', customer: MOCK_CUSTOMERS[2] },
      {
        type: 'alert',
        variant: 'success',
        title: 'Đạt yêu cầu sàng lọc',
        content:
          'Khách hàng đủ điều kiện tiếp tục quy trình cấp tín dụng về mặt tuân thủ. Kết quả sàng lọc có hiệu lực theo kỳ rà soát định kỳ.',
      },
      {
        type: 'disclaimer',
        content:
          'Kết quả sàng lọc trong bản demo là dữ liệu minh hoạ, không phải kết quả đối chiếu danh sách cảnh báo thật.',
      },
    ],
    sources: [MOCK_LOAN_SOURCES[3]],
    suggestions: [
      {
        id: 'sug-comp-next',
        label: 'Kỳ rà soát tiếp theo?',
        prompt: 'Khi nào cần rà soát AML lại cho khách hàng doanh nghiệp?',
      },
    ],
  },
];

/* ------------------------------------------------------------------ */
/* Hội thoại: tra cứu chính sách LTV / DTI                             */
/* ------------------------------------------------------------------ */

export const MOCK_POLICY_MESSAGES: ChatMessage[] = [
  {
    id: 'msg-policy-user-1',
    conversationId: 'conv-ltv-policy',
    role: 'user',
    content: 'Ngưỡng LTV và DTI hiện hành cho sản phẩm vay mua nhà là bao nhiêu?',
    status: 'completed',
    createdAt: nowMinus(480),
  },
  {
    id: 'msg-policy-assistant-1',
    conversationId: 'conv-ltv-policy',
    role: 'assistant',
    content:
      'Theo chính sách cấp tín dụng khách hàng cá nhân hiện hành: DTI tối đa 50%, LTV tối đa 70% với tài sản bảo đảm là bất động sản.',
    status: 'completed',
    createdAt: nowMinus(479),
    blocks: [
      {
        type: 'markdown',
        content: `Theo **Chính sách cấp tín dụng khách hàng cá nhân** hiện hành:`,
      },
      {
        type: 'table',
        title: 'Ngưỡng áp dụng — vay mua nhà',
        columns: [
          { key: 'metric', title: 'Chỉ số', align: 'left' },
          { key: 'threshold', title: 'Ngưỡng', align: 'right' },
          { key: 'note', title: 'Ghi chú', align: 'left' },
        ],
        rows: [
          { metric: 'DTI tối đa', threshold: '50%', note: 'Tính trên tổng nghĩa vụ nợ' },
          { metric: 'LTV tối đa', threshold: '70%', note: 'Tài sản bảo đảm là bất động sản' },
          { metric: 'Điểm tín dụng tối thiểu', threshold: '620', note: 'Theo từng chương trình' },
          { metric: 'Thời hạn tối đa', threshold: '25 năm', note: 'Tuỳ độ tuổi người vay' },
        ],
        footnote: 'Dữ liệu minh hoạ cho bản demo, không phải chính sách chính thức của SHB.',
      },
      {
        type: 'alert',
        variant: 'warning',
        title: 'Trường hợp ngoại lệ',
        content:
          'Hồ sơ vượt ngưỡng phải trình cấp phê duyệt cao hơn và được ghi nhận là phê duyệt ngoại lệ.',
      },
    ],
    sources: [MOCK_LOAN_SOURCES[0], MOCK_LOAN_SOURCES[2]],
    suggestions: [
      {
        id: 'sug-policy-exception',
        label: 'Quy trình phê duyệt ngoại lệ',
        prompt: 'Quy trình phê duyệt ngoại lệ khi hồ sơ vượt ngưỡng DTI là gì?',
      },
    ],
  },
];

/** Bản đồ conversationId -> messages. Hội thoại không có trong map là hội thoại rỗng. */
export const MOCK_MESSAGES_BY_CONVERSATION: Record<string, ChatMessage[]> = {
  [DEMO_LOAN_CONVERSATION_ID]: MOCK_LOAN_MESSAGES,
  'conv-compliance-check': MOCK_COMPLIANCE_MESSAGES,
  'conv-ltv-policy': MOCK_POLICY_MESSAGES,
};
