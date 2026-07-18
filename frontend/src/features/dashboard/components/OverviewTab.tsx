import { useMemo } from 'react';
import { Card, Tag, Typography } from 'antd';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  AuditOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  DeploymentUnitOutlined,
  FileProtectOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { DataTable } from '@/components/tables/DataTable';
import { shbColors } from '@/theme/tokens';
import {
  MOCK_AGENT_METRICS,
  MOCK_AGENT_RUNS,
  MOCK_COLLABORATION,
} from '@/features/chat/constants/mockDashboard';
import { AGENT_LABEL, type AgentRole } from '@/types/agent';
import type { AgentMetric } from '@/types/dashboard';
import styles from '@/pages/AgentDashboardPage.module.css';

const { Text } = Typography;

const AGENT_ICON: Record<AgentRole, React.ReactNode> = {
  planner: <ApartmentOutlined />,
  credit: <AuditOutlined />,
  legal: <SafetyCertificateOutlined />,
  operations: <SettingOutlined />,
  product: <FileProtectOutlined />,
};

export function OverviewTab() {
  const prefersReducedMotion = useReducedMotion();

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

  return (
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
}
