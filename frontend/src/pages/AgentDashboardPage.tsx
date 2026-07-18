import { useMemo, useState } from 'react';
import { Button, Card, Tabs, Tag, Tooltip, Typography } from 'antd';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  AuditOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  DeploymentUnitOutlined,
  FileProtectOutlined,
  RiseOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { SHBLogo } from '@/components/common/SHBLogo';
import { DataTable } from '@/components/tables/DataTable';
import { LazyBaseChart } from '@/components/charts/LazyBaseChart';
import { formatDateTime } from '@/utils/formatDate';
import { shbColors } from '@/theme/tokens';
import {
  COMPARISON_CASE,
  MOCK_AGENT_METRICS,
  MOCK_AGENT_RUNS,
  MOCK_COLLABORATION,
  MOCK_COMPARISON,
  MOCK_COMPARISON_CHART,
} from '@/features/chat/constants/mockDashboard';
import { AGENT_LABEL, AGENT_SHORT_LABEL, type AgentRole } from '@/types/agent';
import {
  TASK_DECISION_LABEL,
  TASK_STATUS_LABEL,
  type AgentMetric,
  type AgentRun,
  type ComparisonMetric,
  type TaskStatus,
} from '@/types/dashboard';
import styles from './AgentDashboardPage.module.css';

const { Text } = Typography;

const AGENT_ICON: Record<AgentRole, React.ReactNode> = {
  planner: <ApartmentOutlined />,
  credit: <AuditOutlined />,
  legal: <SafetyCertificateOutlined />,
  operations: <SettingOutlined />,
  product: <FileProtectOutlined />,
};

const STATUS_COLOR: Record<TaskStatus, string> = {
  running: 'processing',
  completed: 'green',
  failed: 'red',
  escalated: 'gold',
};

/**
 * Dashboard giám sát hệ chuyên gia số.
 *
 * Đáp ứng 2 deliverable của đề bài:
 * 1. "A dashboard showing agent traces, task status, decisions, collaboration flows"
 * 2. "A performance comparison between a single-agent chatbot and the multi-agent system"
 */
export default function AgentDashboardPage() {
  const prefersReducedMotion = useReducedMotion();
  const [tab, setTab] = useState('overview');

  /* ---------------- KPI ---------------- */

  const kpi = useMemo(() => {
    const total = MOCK_AGENT_RUNS.length;
    const completed = MOCK_AGENT_RUNS.filter((r) => r.status === 'completed').length;
    const running = MOCK_AGENT_RUNS.filter((r) => r.status === 'running').length;
    const escalated = MOCK_AGENT_RUNS.filter((r) => r.status === 'escalated').length;
    const failed = MOCK_AGENT_RUNS.filter((r) => r.status === 'failed').length;
    const toolCalls = MOCK_AGENT_RUNS.reduce((sum, r) => sum + r.toolCalls, 0);

    const finished = MOCK_AGENT_RUNS.filter((r) => r.durationMs > 0);
    const avgMs = finished.length
      ? finished.reduce((sum, r) => sum + r.durationMs, 0) / finished.length
      : 0;

    return { total, completed, running, escalated, failed, toolCalls, avgMs };
  }, []);

  /* ---------------- Tab: Tổng quan ---------------- */

  const overviewTab = (
    <>
      <div className={styles.kpiGrid}>
        {[
          {
            label: 'Tổng lượt xử lý',
            icon: <DeploymentUnitOutlined />,
            value: String(kpi.total),
            unit: 'lượt',
          },
          {
            label: 'Hoàn thành',
            icon: <CheckCircleFilled style={{ color: shbColors.semantic.success }} />,
            value: String(kpi.completed),
            unit: `/ ${kpi.total}`,
          },
          {
            label: 'Công cụ đã gọi',
            icon: <ToolOutlined />,
            value: String(kpi.toolCalls),
            unit: 'lần',
            accent: true,
          },
          {
            label: 'Thời gian trung bình',
            icon: <ClockCircleOutlined />,
            value: (kpi.avgMs / 1000).toFixed(1),
            unit: 'giây',
          },
        ].map((item, index) => (
          <motion.div
            key={item.label}
            className={styles.kpi}
            initial={prefersReducedMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
          >
            <span className={styles.kpiLabel}>
              {item.icon}
              {item.label}
            </span>
            <span className={[styles.kpiValue, item.accent ? styles.kpiAccent : ''].join(' ')}>
              {item.value} <span className={styles.kpiUnit}>{item.unit}</span>
            </span>
          </motion.div>
        ))}
      </div>

      <Card
        className={styles.section}
        title="Hiệu năng theo từng chuyên gia số"
        size="small"
        extra={<Text type="secondary" style={{ fontSize: 12 }}>Dữ liệu minh hoạ</Text>}
      >
        <DataTable<AgentMetric>
          rowKey="agent"
          dataSource={MOCK_AGENT_METRICS}
          size="small"
          columns={[
            {
              title: 'Chuyên gia số',
              dataIndex: 'agent',
              key: 'agent',
              render: (agent: AgentRole) => (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  {AGENT_ICON[agent]}
                  {AGENT_LABEL[agent]}
                </span>
              ),
            },
            { title: 'Số tác vụ', dataIndex: 'tasks', key: 'tasks', align: 'right' },
            {
              title: 'Tỉ lệ thành công',
              dataIndex: 'successRate',
              key: 'successRate',
              align: 'right',
              render: (value: number) => (
                <Tag color={value >= 95 ? 'green' : value >= 85 ? 'gold' : 'red'}>{value}%</Tag>
              ),
            },
            {
              title: 'Thời gian TB',
              dataIndex: 'avgDurationMs',
              key: 'avgDurationMs',
              align: 'right',
              render: (ms: number) => `${(ms / 1000).toFixed(2)}s`,
            },
            { title: 'Công cụ gọi', dataIndex: 'toolCalls', key: 'toolCalls', align: 'right' },
          ]}
        />
      </Card>

      <Card className={styles.section} title="Luồng cộng tác giữa các chuyên gia số" size="small">
        <p className={styles.sectionDesc}>
          Planner phân rã yêu cầu và bàn giao cho các chuyên gia thực thi, sau đó tổng hợp kết quả.
        </p>

        <div className={styles.flow}>
          <div className={styles.flowPlanner}>
            <span className={styles.flowIcon} aria-hidden="true">
              <ApartmentOutlined />
            </span>
            <span className={styles.flowName}>Planner</span>
            <span className={styles.flowMeta}>Điều phối</span>
          </div>

          <div className={styles.flowArrow} aria-hidden="true">
            <ArrowRightOutlined />
            <span className={styles.flowArrowLabel}>giao việc</span>
          </div>

          <div className={styles.flowSpecialists}>
            {(['credit', 'legal', 'product', 'operations'] as AgentRole[]).map((agent) => {
              const edge = MOCK_COLLABORATION.find((e) => e.from === 'planner' && e.to === agent);
              return (
                <div key={agent} className={styles.flowNode}>
                  <span className={styles.flowIcon} aria-hidden="true">
                    {AGENT_ICON[agent]}
                  </span>
                  <span className={styles.flowBody}>
                    <span className={styles.flowName}>{AGENT_LABEL[agent]}</span>
                    <span className={styles.flowMeta}>{edge?.count ?? 0} lượt bàn giao</span>
                  </span>
                </div>
              );
            })}
          </div>

          <div className={styles.flowArrow} aria-hidden="true">
            <ArrowLeftOutlined />
            <span className={styles.flowArrowLabel}>trả kết quả</span>
          </div>
        </div>
      </Card>
    </>
  );

  /* ---------------- Tab: Agent traces ---------------- */

  const tracesTab = (
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

  /* ---------------- Tab: So sánh ---------------- */

  const comparisonTab = (
    <>
      <div className={styles.cmpHead}>
        <ThunderboltOutlined />
        <span>
          Cùng một hồ sơ: <strong>{COMPARISON_CASE}</strong>
        </span>
      </div>

      <Card
        className={styles.section}
        title="Độ phủ thẩm định — đơn agent so với đa agent"
        size="small"
      >
        <p className={styles.sectionDesc}>
          Hai hệ vẽ trên <strong>cùng một trục</strong> để so sánh trực tiếp — cột cao hơn nghĩa là
          làm được nhiều hơn.
        </p>

        {/*
          Cố ý dùng MỘT chart nhóm thay vì hai chart riêng: hai chart có thang trục
          độc lập sẽ khiến cột giá trị 2 trông cao ngang cột giá trị 5 → đọc sai.
        */}
        <LazyBaseChart<(typeof MOCK_COMPARISON_CHART)[number]>
          type="column"
          data={MOCK_COMPARISON_CHART}
          height={300}
          ariaLabel="Biểu đồ cột nhóm so sánh: Chốt kiểm tra — đơn agent 2, đa agent 5. Công cụ gọi — đơn agent 1, đa agent 5. Nguồn trích dẫn — đơn agent 0, đa agent 3."
          config={{
            xField: 'category',
            yField: 'value',
            colorField: 'series',
            group: true,
            scale: { color: { range: [shbColors.navy[300], shbColors.orange[500]] } },
            legend: { color: { position: 'top' } },
            style: { radiusTopLeft: 5, radiusTopRight: 5, maxWidth: 46 },
            axis: { y: { title: 'Số lượng' } },
          }}
        />
      </Card>

      <Card className={styles.section} title="So sánh chi tiết" size="small">
        <DataTable<ComparisonMetric>
          rowKey="id"
          dataSource={MOCK_COMPARISON}
          size="small"
          columns={[
            {
              title: 'Chỉ tiêu',
              dataIndex: 'label',
              key: 'label',
              render: (label: string, record) => (
                <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontWeight: 550 }}>{label}</span>
                  <Text type="secondary" style={{ fontSize: 11.5 }}>
                    {record.description}
                  </Text>
                </span>
              ),
            },
            {
              title: 'Chatbot đơn agent',
              dataIndex: 'singleAgent',
              key: 'singleAgent',
              render: (value: string, record) => (
                <span className={styles.winnerCell}>
                  {record.winner === 'single' && (
                    <CheckCircleFilled style={{ color: shbColors.semantic.success }} />
                  )}
                  {value}
                </span>
              ),
            },
            {
              title: 'Hệ đa agent',
              dataIndex: 'multiAgent',
              key: 'multiAgent',
              render: (value: string, record) => (
                <span className={styles.winnerCell}>
                  {record.winner === 'multi' && (
                    <CheckCircleFilled style={{ color: shbColors.semantic.success }} />
                  )}
                  <strong>{value}</strong>
                </span>
              ),
            },
          ]}
        />

        <div className={styles.verdict}>
          <h4 className={styles.verdictTitle}>Kết luận</h4>
          <p className={styles.verdictText}>
            Hệ đa agent thắng ở <strong>6/7 chỉ tiêu</strong>. Đơn agent chỉ nhanh hơn về thời gian
            phản hồi (~1,2s so với ~4,0s) — đây là <strong>đánh đổi có chủ đích</strong>: hệ đa agent
            dùng thêm thời gian để gọi 5 công cụ, đối chiếu đủ 5 chốt kiểm tra và trích dẫn 3 nguồn.
            Với nghiệp vụ tín dụng, độ chính xác và khả năng truy vết quan trọng hơn vài giây phản
            hồi. Quan trọng nhất: đơn agent <strong>không phát hiện</strong> khoản vay vượt hạn mức
            phê duyệt, còn hệ đa agent tự động chặn và trình cấp cao hơn.
          </p>
        </div>
      </Card>
    </>
  );

  /* ---------------- Render ---------------- */

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <SHBLogo size="small" showProductName />
        <Link to="/">
          <Button icon={<ArrowLeftOutlined />}>Về giao diện trò chuyện</Button>
        </Link>
      </header>

      <div className={styles.container}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Giám sát hệ chuyên gia số</h1>
          <p className={styles.subtitle}>
            Theo dõi tiến trình, quyết định và luồng cộng tác giữa các agent chuyên môn.
          </p>
        </div>

        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: 'overview',
              label: (
                <span>
                  <RiseOutlined /> Tổng quan
                </span>
              ),
              children: overviewTab,
            },
            {
              key: 'traces',
              label: (
                <span>
                  <DeploymentUnitOutlined /> Agent traces
                </span>
              ),
              children: tracesTab,
            },
            {
              key: 'comparison',
              label: (
                <span>
                  <ThunderboltOutlined /> So sánh hiệu năng
                </span>
              ),
              children: comparisonTab,
            },
          ]}
        />
      </div>
    </div>
  );
}
