import { Card, Typography } from 'antd';
import { CheckCircleFilled, ThunderboltOutlined } from '@ant-design/icons';
import { DataTable } from '@/components/tables/DataTable';
import { LazyBaseChart } from '@/components/charts/LazyBaseChart';
import { shbColors } from '@/theme/tokens';
import {
  COMPARISON_CASE,
  MOCK_COMPARISON,
  MOCK_COMPARISON_CHART,
} from '@/features/chat/constants/mockDashboard';
import type { ComparisonMetric } from '@/types/dashboard';
import styles from '@/pages/AgentDashboardPage.module.css';

const { Text } = Typography;

export function ComparisonTab() {
  return (
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
}
