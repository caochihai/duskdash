import type { AgentRole, AgentTrace } from './agent';

/**
 * Types cho Dashboard giám sát hệ chuyên gia số.
 * Đáp ứng deliverable: "A dashboard showing agent traces, task status,
 * decisions, and collaboration flows".
 */

export type TaskStatus = 'running' | 'completed' | 'failed' | 'escalated';

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  running: 'Đang xử lý',
  completed: 'Hoàn thành',
  failed: 'Lỗi',
  escalated: 'Trình cấp trên',
};

export type TaskDecision = 'approved' | 'rejected' | 'need-info' | 'escalated' | 'none';

export const TASK_DECISION_LABEL: Record<TaskDecision, string> = {
  approved: 'Đề xuất duyệt',
  rejected: 'Đề xuất từ chối',
  'need-info': 'Cần bổ sung',
  escalated: 'Vượt hạn mức',
  none: 'Không có quyết định',
};

/** Một lượt chạy của hệ agent cho một yêu cầu. */
export interface AgentRun {
  id: string;
  /** Yêu cầu gốc của chuyên viên. */
  request: string;
  /** Hồ sơ liên quan, nếu có. */
  reference?: string;
  status: TaskStatus;
  decision: TaskDecision;
  /** Các agent đã tham gia. */
  agents: AgentRole[];
  startedAt: string;
  durationMs: number;
  /** Số công cụ đã gọi. */
  toolCalls: number;
  trace: AgentTrace;
}

/** Chỉ số hiệu năng theo từng agent. */
export interface AgentMetric {
  agent: AgentRole;
  tasks: number;
  /** Tỉ lệ hoàn thành thành công, %. */
  successRate: number;
  /** Thời gian xử lý trung bình, ms. */
  avgDurationMs: number;
  toolCalls: number;
}

/** Một cạnh trong luồng cộng tác giữa các agent. */
export interface CollaborationEdge {
  from: AgentRole;
  to: AgentRole;
  /** Số lần bàn giao công việc. */
  count: number;
}

/** Một chỉ tiêu trong bảng so sánh single-agent vs multi-agent. */
export interface ComparisonMetric {
  id: string;
  label: string;
  description: string;
  singleAgent: string;
  multiAgent: string;
  /** Hệ nào tốt hơn ở chỉ tiêu này. */
  winner: 'single' | 'multi' | 'tie';
}
