/**
 * Multi-agent types — theo đề bài "Digital Expert Agents".
 *
 * Mỗi agent là một chuyên gia số của một nghiệp vụ ngân hàng. Planner phân rã
 * công việc và giao cho các specialist executor.
 */

export type AgentRole = 'planner' | 'credit' | 'legal' | 'operations' | 'product';

export const AGENT_LABEL: Record<AgentRole, string> = {
  planner: 'Điều phối',
  credit: 'Chuyên gia Tín dụng',
  legal: 'Pháp chế & Tuân thủ',
  operations: 'Vận hành',
  product: 'Sản phẩm',
};

export const AGENT_SHORT_LABEL: Record<AgentRole, string> = {
  planner: 'Planner',
  credit: 'Credit',
  legal: 'Legal',
  operations: 'Operations',
  product: 'Product',
};

export type AgentStepStatus = 'pending' | 'running' | 'success' | 'error';

/** Một lần agent gọi công cụ (tool use / function calling). */
export interface AgentToolCall {
  name: string;
  /** Nhãn hiển thị cho người dùng, ví dụ "Truy vấn hồ sơ tín dụng". */
  label: string;
  /** Tóm tắt kết quả trả về — an toàn để hiển thị. */
  result?: string;
}

/**
 * Một bước trong chuỗi xử lý của hệ thống agent.
 *
 * Đây là **agent trace** phục vụ giám sát vận hành, KHÔNG phải chain-of-thought
 * nội bộ của mô hình: chỉ nêu hành động, công cụ đã gọi và kết quả.
 */
export interface AgentTraceStep {
  id: string;
  agent: AgentRole;
  title: string;
  description?: string;
  status: AgentStepStatus;
  tool?: AgentToolCall;
  durationMs?: number;
}

/** Toàn bộ phiên xử lý của hệ agent cho một yêu cầu. */
export interface AgentTrace {
  /** Tóm tắt kế hoạch do Planner đưa ra. */
  summary: string;
  steps: AgentTraceStep[];
}
