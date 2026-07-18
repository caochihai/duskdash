import { useState } from 'react';
import { Button, Tabs } from 'antd';
import {
  ArrowLeftOutlined,
  DeploymentUnitOutlined,
  RiseOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { SHBLogo } from '@/components/common/SHBLogo';
import { OverviewTab, TracesTab, ComparisonTab } from '@/features/dashboard/components';
import styles from './AgentDashboardPage.module.css';

/**
 * Dashboard giám sát hệ chuyên gia số.
 *
 * Đáp ứng 2 deliverable của đề bài:
 * 1. "A dashboard showing agent traces, task status, decisions, collaboration flows"
 * 2. "A performance comparison between a single-agent chatbot and the multi-agent system"
 */
export default function AgentDashboardPage() {
  const [tab, setTab] = useState('overview');

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
              children: <OverviewTab />,
            },
            {
              key: 'traces',
              label: (
                <span>
                  <DeploymentUnitOutlined /> Agent traces
                </span>
              ),
              children: <TracesTab />,
            },
            {
              key: 'comparison',
              label: (
                <span>
                  <ThunderboltOutlined /> So sánh hiệu năng
                </span>
              ),
              children: <ComparisonTab />,
            },
          ]}
        />
      </div>
    </div>
  );
}
