import { Card, Tag, Tooltip, Typography } from 'antd';
import { DataTable } from '@/components/tables/DataTable';
import { formatDateTime } from '@/utils/formatDate';
import { MOCK_AGENT_RUNS } from '@/features/chat/constants/mockDashboard';
import { AGENT_LABEL, AGENT_SHORT_LABEL, type AgentRole } from '@/types/agent';
import {
  TASK_DECISION_LABEL,
  TASK_STATUS_LABEL,
  type AgentRun,
  type TaskStatus,
} from '@/types/dashboard';

const { Text } = Typography;

const STATUS_COLOR: Record<TaskStatus, string> = {
  running: 'processing',
  completed: 'green',
  failed: 'red',
  escalated: 'gold',
};

export function TracesTab() {
  return (
    <Card
      title="Lượt xử lý gần đây"
      size="small"
      extra={<Text type="secondary" style={{ fontSize: 12 }}>{MOCK_AGENT_RUNS.length} lượt</Text>}
    >
      <DataTable<AgentRun>
        rowKey="id"
        dataSource={MOCK_AGENT_RUNS}
        size="small"
        columns={[
          {
            title: 'Yêu cầu',
            dataIndex: 'request',
            key: 'request',
            render: (request: string, record) => (
              <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontWeight: 550 }}>{request}</span>
                {record.reference && (
                  <Text type="secondary" style={{ fontSize: 11.5 }}>
                    {record.reference}
                  </Text>
                )}
              </span>
            ),
          },
          {
            title: 'Chuyên gia tham gia',
            dataIndex: 'agents',
            key: 'agents',
            render: (agents: AgentRole[]) => (
              <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {agents.map((agent) => (
                  <Tooltip key={agent} title={AGENT_LABEL[agent]}>
                    <Tag bordered={false} style={{ marginInlineEnd: 0 }}>
                      {AGENT_SHORT_LABEL[agent]}
                    </Tag>
                  </Tooltip>
                ))}
              </span>
            ),
          },
          {
            title: 'Trạng thái',
            dataIndex: 'status',
            key: 'status',
            render: (status: TaskStatus) => (
              <Tag color={STATUS_COLOR[status]}>{TASK_STATUS_LABEL[status]}</Tag>
            ),
          },
          {
            title: 'Quyết định',
            dataIndex: 'decision',
            key: 'decision',
            render: (decision: AgentRun['decision']) => (
              <Text type={decision === 'none' ? 'secondary' : undefined} style={{ fontSize: 13 }}>
                {TASK_DECISION_LABEL[decision]}
              </Text>
            ),
          },
          {
            title: 'Công cụ',
            dataIndex: 'toolCalls',
            key: 'toolCalls',
            align: 'right',
          },
          {
            title: 'Thời gian',
            dataIndex: 'durationMs',
            key: 'durationMs',
            align: 'right',
            render: (ms: number) => (ms > 0 ? `${(ms / 1000).toFixed(2)}s` : '—'),
          },
          {
            title: 'Bắt đầu',
            dataIndex: 'startedAt',
            key: 'startedAt',
            render: (iso: string) => (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {formatDateTime(iso)}
              </Text>
            ),
          },
        ]}
      />
    </Card>
  );
}
