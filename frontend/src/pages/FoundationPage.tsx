import { Avatar, Badge, Button, Card, Space, Tag, Typography } from 'antd';
import { ArrowLeftOutlined, CheckCircleFilled, ThunderboltOutlined } from '@ant-design/icons';
import { Bubble } from '@ant-design/x';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { BaseChart } from '@/components/charts/BaseChart';
import { DataTable } from '@/components/tables/DataTable';
import { SHBLogo } from '@/components/common/SHBLogo';
import { StatusBadge } from '@/components/common/StatusBadge';
import apiClient, { USE_MOCK_API } from '@/services/apiClient';
import { shbChartPalette } from '@/components/charts/chartPalette';
import styles from './FoundationPage.module.css';

const { Text, Paragraph } = Typography;

interface ChartRow {
  category: string;
  value: number;
}

interface TableRow {
  id: string;
  library: string;
  role: string;
  status: string;
}

const CHART_DATA: ChartRow[] = [
  { category: 'Tháng 1', value: 32 },
  { category: 'Tháng 2', value: 48 },
  { category: 'Tháng 3', value: 41 },
  { category: 'Tháng 4', value: 57 },
];

const TABLE_DATA: TableRow[] = [
  { id: 'vite', library: 'Vite', role: 'Dev server & build', status: 'Hoạt động' },
  { id: 'react', library: 'React', role: 'Component & state', status: 'Hoạt động' },
  { id: 'router', library: 'React Router', role: 'Routing tập trung', status: 'Hoạt động' },
  { id: 'antd', library: 'Ant Design', role: 'UI ứng dụng chuẩn', status: 'Hoạt động' },
  { id: 'antd-x', library: 'Ant Design X', role: 'Thành phần AI', status: 'Hoạt động' },
  { id: 'charts', library: 'Ant Design Charts', role: 'Biểu đồ', status: 'Hoạt động' },
  { id: 'query', library: 'TanStack Query', role: 'Server state', status: 'Hoạt động' },
  { id: 'axios', library: 'Axios', role: 'HTTP client', status: 'Hoạt động' },
  { id: 'motion', library: 'Motion for React', role: 'Chuyển động', status: 'Hoạt động' },
];

/**
 * Trang kiểm chứng nền tảng.
 * Không phải giao diện chính — chỉ xác nhận các thư viện đã tích hợp đúng.
 */
export default function FoundationPage() {
  // Kiểm chứng TanStack Query thực sự chạy (không gọi mạng).
  const probeQuery = useQuery({
    queryKey: ['foundation', 'probe'],
    queryFn: async () => {
      await new Promise((resolve) => setTimeout(resolve, 220));
      return { ok: true, at: new Date().toISOString() };
    },
  });

  // Kiểm chứng Axios instance đã khởi tạo với baseURL từ biến môi trường.
  const axiosBaseUrl = apiClient.defaults.baseURL ?? '(chưa cấu hình)';

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.header}>
          <SHBLogo size="medium" showProductName />
          <Link to="/">
            <Button icon={<ArrowLeftOutlined />}>Về giao diện chính</Button>
          </Link>
        </div>

        <h1 className={styles.title}>Foundation Page</h1>
        <p className={styles.subtitle}>
          Trang kiểm chứng các thư viện nền tảng đã được tích hợp thành công.
        </p>

        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div className={styles.grid}>
            {/* React Router */}
            <Card title="React Router" size="small">
              <div className={styles.statusRow}>
                <CheckCircleFilled style={{ color: '#15805D' }} />
                <Text>Route `/` và `*` khai báo tại `src/app/routes.tsx`</Text>
              </div>
            </Card>

            {/* Ant Design + Icons */}
            <Card title="Ant Design + Icons" size="small">
              <Space wrap>
                <Button type="primary" icon={<ThunderboltOutlined />}>
                  Button
                </Button>
                <Tag color="orange">Tag</Tag>
                <Badge count={5} />
                <StatusBadge tone="online" label="Đang hoạt động" />
              </Space>
            </Card>

            {/* TanStack Query */}
            <Card title="TanStack Query" size="small" loading={probeQuery.isLoading}>
              <div className={styles.statusRow}>
                <CheckCircleFilled style={{ color: '#15805D' }} />
                <Text>
                  Query trạng thái: <Text code>{probeQuery.status}</Text>
                </Text>
              </div>
            </Card>

            {/* Axios */}
            <Card title="Axios" size="small">
              <Paragraph style={{ marginBottom: 4 }}>
                <Text type="secondary">baseURL (VITE_API_BASE_URL):</Text>
              </Paragraph>
              <Text code>{axiosBaseUrl}</Text>
              <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
                <Tag color={USE_MOCK_API ? 'orange' : 'blue'}>
                  {USE_MOCK_API ? 'Mock API đang bật' : 'Đang dùng API thật'}
                </Tag>
              </Paragraph>
            </Card>

            {/* Motion */}
            <Card title="Motion for React" size="small">
              <motion.div
                animate={{ x: [0, 12, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'linear-gradient(135deg, #F37021, #F88C46)',
                }}
              />
            </Card>

            {/* Theme + CSS Modules */}
            <Card title="Theme SHB + CSS Modules" size="small">
              <div className={styles.cssProof}>
                Khối này dùng CSS Modules + CSS variable từ design token
                (<Text code>#F37021</Text> / <Text code>#2F2E79</Text>).
              </div>
            </Card>
          </div>

          {/* Ant Design X */}
          <Card title="Ant Design X — Bubble" size="small">
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Bubble placement="end" content="Ant Design X đã hoạt động chưa?" />
              <Bubble
                placement="start"
                avatar={
                  <Avatar icon={<ThunderboltOutlined />} style={{ background: '#FFF7F0', color: '#F37021' }} />
                }
                content="Đã hoạt động. Sender, Bubble và Conversations đều sẵn sàng."
              />
            </Space>
          </Card>

          {/* Ant Design Charts qua BaseChart adapter */}
          <Card title="Ant Design Charts — qua BaseChart adapter" size="small">
            <BaseChart<ChartRow>
              type="column"
              data={CHART_DATA}
              height={220}
              ariaLabel="Biểu đồ cột minh hoạ: Tháng 1 32, Tháng 2 48, Tháng 3 41, Tháng 4 57."
              config={{
                xField: 'category',
                yField: 'value',
                colorField: 'category',
                scale: { color: { range: shbChartPalette } },
                legend: false,
                style: { radiusTopLeft: 6, radiusTopRight: 6, maxWidth: 56 },
              }}
            />
          </Card>

          {/* Ant Design Table qua DataTable adapter */}
          <Card title="Ant Design Table — qua DataTable adapter" size="small">
            <DataTable<TableRow>
              rowKey="id"
              dataSource={TABLE_DATA}
              size="small"
              columns={[
                { title: 'Thư viện', dataIndex: 'library', key: 'library' },
                { title: 'Vai trò', dataIndex: 'role', key: 'role' },
                {
                  title: 'Trạng thái',
                  dataIndex: 'status',
                  key: 'status',
                  render: (value: string) => <Tag color="green">{value}</Tag>,
                },
              ]}
            />
          </Card>
        </Space>
      </div>
    </div>
  );
}
