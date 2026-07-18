import type {
  AgentMetric,
  AgentRun,
  CollaborationEdge,
  ComparisonMetric,
} from '@/types/dashboard';

/**
 * Dữ liệu giám sát hệ chuyên gia số — DỮ LIỆU MINH HOẠ cho bản demo.
 * Khi có backend, phần này sẽ đến từ hệ thống tracing thật.
 */

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60 * 1000).toISOString();
}

export const MOCK_AGENT_RUNS: AgentRun[] = [
  {
    id: 'run-001',
    request: 'Thẩm định hồ sơ vay HS-2026-0481',
    reference: 'HS-2026-0481',
    status: 'completed',
    decision: 'approved',
    agents: ['planner', 'credit', 'legal', 'product', 'operations'],
    startedAt: minutesAgo(63),
    durationMs: 4_020,
    toolCalls: 5,
    trace: { summary: 'Điều phối 4 chuyên gia số', steps: [] },
  },
  {
    id: 'run-002',
    request: 'Thẩm định hồ sơ vay HS-2026-0492',
    reference: 'HS-2026-0492',
    status: 'completed',
    decision: 'rejected',
    agents: ['planner', 'credit', 'legal', 'operations'],
    startedAt: minutesAgo(48),
    durationMs: 3_640,
    toolCalls: 4,
    trace: { summary: 'Điều phối 3 chuyên gia số', steps: [] },
  },
  {
    id: 'run-003',
    request: 'Thẩm định hồ sơ vay HS-2026-0455 (5 tỷ)',
    reference: 'HS-2026-0455',
    status: 'escalated',
    decision: 'escalated',
    agents: ['planner', 'credit', 'legal', 'operations'],
    startedAt: minutesAgo(35),
    durationMs: 4_510,
    toolCalls: 5,
    trace: { summary: 'Vượt hạn mức — trình Hội đồng tín dụng', steps: [] },
  },
  {
    id: 'run-004',
    request: 'Sàng lọc AML/KYC — Công ty Minh Phát',
    reference: 'CIF-9920477',
    status: 'completed',
    decision: 'approved',
    agents: ['planner', 'legal', 'operations'],
    startedAt: minutesAgo(28),
    durationMs: 1_840,
    toolCalls: 2,
    trace: { summary: 'Sàng lọc tuân thủ', steps: [] },
  },
  {
    id: 'run-005',
    request: 'Tra cứu ngưỡng LTV/DTI vay mua nhà',
    status: 'completed',
    decision: 'none',
    agents: ['planner', 'product'],
    startedAt: minutesAgo(19),
    durationMs: 980,
    toolCalls: 1,
    trace: { summary: 'Tra cứu chính sách', steps: [] },
  },
  {
    id: 'run-006',
    request: 'Tra cứu hồ sơ khách hàng CIF-8842019',
    reference: 'CIF-8842019',
    status: 'completed',
    decision: 'none',
    agents: ['planner', 'operations', 'credit'],
    startedAt: minutesAgo(12),
    durationMs: 1_390,
    toolCalls: 2,
    trace: { summary: 'Tra cứu hồ sơ khách hàng', steps: [] },
  },
  {
    id: 'run-007',
    request: 'Kiểm tra chứng từ HS-2026-0492',
    reference: 'HS-2026-0492',
    status: 'failed',
    decision: 'need-info',
    agents: ['planner', 'operations'],
    startedAt: minutesAgo(7),
    durationMs: 2_110,
    toolCalls: 2,
    trace: { summary: 'Thiếu sao kê lương 3 tháng', steps: [] },
  },
  {
    id: 'run-008',
    request: 'Quy trình bảo lãnh dự thầu',
    status: 'running',
    decision: 'none',
    agents: ['planner', 'legal', 'operations'],
    startedAt: minutesAgo(1),
    durationMs: 0,
    toolCalls: 1,
    trace: { summary: 'Đang tra cứu quy trình', steps: [] },
  },
];

export const MOCK_AGENT_METRICS: AgentMetric[] = [
  { agent: 'planner', tasks: 8, successRate: 100, avgDurationMs: 340, toolCalls: 3 },
  { agent: 'credit', tasks: 4, successRate: 92, avgDurationMs: 1_180, toolCalls: 6 },
  { agent: 'legal', tasks: 5, successRate: 96, avgDurationMs: 880, toolCalls: 5 },
  { agent: 'product', tasks: 3, successRate: 100, avgDurationMs: 540, toolCalls: 3 },
  { agent: 'operations', tasks: 6, successRate: 84, avgDurationMs: 660, toolCalls: 5 },
];

/** Luồng bàn giao công việc giữa các agent. */
export const MOCK_COLLABORATION: CollaborationEdge[] = [
  { from: 'planner', to: 'credit', count: 4 },
  { from: 'planner', to: 'legal', count: 5 },
  { from: 'planner', to: 'product', count: 3 },
  { from: 'planner', to: 'operations', count: 6 },
  { from: 'credit', to: 'planner', count: 4 },
  { from: 'legal', to: 'planner', count: 5 },
  { from: 'product', to: 'planner', count: 3 },
  { from: 'operations', to: 'planner', count: 6 },
  { from: 'credit', to: 'legal', count: 2 },
];

/**
 * So sánh chatbot đơn agent với hệ chuyên gia số đa agent
 * trên cùng một hồ sơ (HS-2026-0481).
 *
 * Đáp ứng deliverable: "A performance comparison between a single-agent chatbot
 * and the multi-agent system".
 */
export const COMPARISON_CASE = 'HS-2026-0481 — Vay mua nhà 2 tỷ, Trần Thị Hồng Nhung';

export const MOCK_COMPARISON: ComparisonMetric[] = [
  {
    id: 'cmp-coverage',
    label: 'Số chốt kiểm tra thực hiện',
    description: 'Số tiêu chí thẩm định được đối chiếu với chính sách.',
    singleAgent: '2/5',
    multiAgent: '5/5',
    winner: 'multi',
  },
  {
    id: 'cmp-tools',
    label: 'Công cụ được gọi',
    description: 'Truy vấn dữ liệu thật thay vì chỉ sinh văn bản.',
    singleAgent: '1',
    multiAgent: '5',
    winner: 'multi',
  },
  {
    id: 'cmp-domain',
    label: 'Phạm vi chuyên môn',
    description: 'Số lĩnh vực nghiệp vụ được bao phủ.',
    singleAgent: 'Tổng quát',
    multiAgent: 'Tín dụng, Pháp chế, Sản phẩm, Vận hành',
    winner: 'multi',
  },
  {
    id: 'cmp-latency',
    label: 'Thời gian phản hồi',
    description: 'Đơn agent nhanh hơn vì làm ít việc hơn — đây là đánh đổi có chủ đích.',
    singleAgent: '~1,2s',
    multiAgent: '~4,0s',
    winner: 'single',
  },
  {
    id: 'cmp-action',
    label: 'Hành động thực thi',
    description: 'Có tạo ra hành động nghiệp vụ hay chỉ trả lời văn bản.',
    singleAgent: 'Chỉ trả lời',
    multiAgent: 'Trình quyết định phê duyệt',
    winner: 'multi',
  },
  {
    id: 'cmp-audit',
    label: 'Khả năng truy vết',
    description: 'Có ghi lại căn cứ và nguồn cho từng kết luận không.',
    singleAgent: 'Không',
    multiAgent: 'Đầy đủ trace + nguồn',
    winner: 'multi',
  },
  {
    id: 'cmp-escalation',
    label: 'Nhận biết vượt hạn mức',
    description: 'Có phát hiện khoản vay vượt thẩm quyền chuyên viên không.',
    singleAgent: 'Không',
    multiAgent: 'Có — tự động chặn',
    winner: 'multi',
  },
];

/** Dữ liệu chart so sánh độ phủ thẩm định. */
export const MOCK_COMPARISON_CHART = [
  { category: 'Chốt kiểm tra', value: 2, series: 'Đơn agent' },
  { category: 'Chốt kiểm tra', value: 5, series: 'Đa agent' },
  { category: 'Công cụ gọi', value: 1, series: 'Đơn agent' },
  { category: 'Công cụ gọi', value: 5, series: 'Đa agent' },
  { category: 'Nguồn trích dẫn', value: 0, series: 'Đơn agent' },
  { category: 'Nguồn trích dẫn', value: 3, series: 'Đa agent' },
];
