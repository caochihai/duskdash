import { useMemo, useState } from 'react';
import { Avatar, Button, Empty, Tag, Tooltip } from 'antd';
import {
  ArrowLeftOutlined,
  CloseOutlined,
  ExpandAltOutlined,
  ShopOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { CustomerRecordGrid } from './CustomerRecordGrid';
import { LoanApprovalCard } from './LoanApprovalCard';
import { formatCurrency, formatRate } from '@/utils/formatCurrency';
import { shbColors } from '@/theme/tokens';
import {
  LOAN_STATUS_COLOR,
  LOAN_STATUS_LABEL,
  RISK_LABEL,
  type Customer,
  type LoanApplication,
  type LoanApplicationStatus,
} from '@/types/customer';

import styles from './CustomerWorkspacePanel.module.css';

export interface CustomerWorkspacePanelProps {
  customer: Customer;
  records: LoanApplication[];
  onClose: () => void;
  /** Mở trang hồ sơ đầy đủ (/customer/:id). */
  onOpenFullPage: (customer: Customer) => void;
  /** Đưa các hồ sơ đã chọn vào chat cho hệ chuyên gia số thẩm định. */
  onReviewInChat: (records: LoanApplication[]) => void;
  onLoanDecision: (
    application: LoanApplication,
    status: LoanApplicationStatus,
    note: string,
  ) => void;
}

const RISK_COLOR: Record<Customer['riskLevel'], string> = {
  low: 'green',
  medium: 'gold',
  high: 'red',
};

type PanelView = 'grid' | 'compare' | 'detail';

/**
 * Panel làm việc với khách hàng — chiếm nửa màn hình bên phải, chat vẫn dùng
 * được ở nửa trái (giống split-view khi mở tài liệu).
 *
 * Ba chế độ xem:
 * - grid    : lưới hồ sơ, chọn nhiều
 * - compare : bảng so sánh các hồ sơ đã chọn
 * - detail  : mở chi tiết + thẻ phê duyệt từng hồ sơ đã chọn
 */
export function CustomerWorkspacePanel({
  customer,
  records,
  onClose,
  onOpenFullPage,
  onReviewInChat,
  onLoanDecision,
}: CustomerWorkspacePanelProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [view, setView] = useState<PanelView>('grid');

  const pendingCount = records.filter(
    (r) => r.status === 'pending' || r.status === 'need-info',
  ).length;

  const selectedRecords = useMemo(
    () => records.filter((r) => selectedIds.includes(r.id)),
    [records, selectedIds],
  );

  const toggle = (id: string) =>
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );

  const toggleAll = (select: boolean) =>
    setSelectedIds(select ? records.map((r) => r.id) : []);

  const handleReview = () => {
    onReviewInChat(selectedRecords);
    setSelectedIds([]);
  };

  return (
    <aside className={styles.panel} aria-label={`Hồ sơ khách hàng ${customer.fullName}`}>
      <div className={styles.header}>
        <Avatar
          className={styles.headerAvatar}
          size={38}
          icon={customer.segment === 'business' ? <ShopOutlined /> : <UserOutlined />}
          style={{ background: shbColors.navy[100], color: shbColors.navy[700] }}
        />
        <div className={styles.headerBody}>
          <span className={styles.headerName}>{customer.fullName}</span>
          <span className={styles.headerMeta}>
            {customer.code} • {customer.branch}
          </span>
        </div>
        <div className={styles.headerActions}>
          <Tag color={RISK_COLOR[customer.riskLevel]} style={{ marginInlineEnd: 4 }}>
            {RISK_LABEL[customer.riskLevel]}
          </Tag>
          <Tooltip title="Mở trang hồ sơ đầy đủ">
            <Button
              type="text"
              icon={<ExpandAltOutlined />}
              onClick={() => onOpenFullPage(customer)}
              aria-label="Mở trang hồ sơ đầy đủ"
            />
          </Tooltip>
          <Tooltip title="Đóng">
            <Button
              type="text"
              icon={<CloseOutlined />}
              onClick={onClose}
              aria-label="Đóng panel hồ sơ"
            />
          </Tooltip>
        </div>
      </div>

      <div className={styles.body}>
        {/* Chỉ số nhanh — luôn hiển thị */}
        {view === 'grid' && (
          <div className={styles.stats}>
            <div className={styles.stat}>
              <div className={styles.statLabel}>Chờ xử lý</div>
              <div className={[styles.statValue, styles.statAccent].join(' ')}>{pendingCount}</div>
            </div>
            <div className={styles.stat}>
              <div className={styles.statLabel}>Điểm TD</div>
              <div className={styles.statValue}>{customer.creditScore}</div>
            </div>
            <div className={styles.stat}>
              <div className={styles.statLabel}>DTI</div>
              <div className={styles.statValue}>{customer.dti}%</div>
            </div>
          </div>
        )}

        {/* --- Lưới hồ sơ --- */}
        {view === 'grid' &&
          (records.length ? (
            <>
              <h3 className={styles.sectionTitle}>Hồ sơ liên quan</h3>
              <CustomerRecordGrid
                records={records}
                selectedIds={selectedIds}
                onToggle={toggle}
                onToggleAll={toggleAll}
                onReviewSelected={handleReview}
                onOpenSelected={() => setView('detail')}
                onCompareSelected={() => setView('compare')}
              />
            </>
          ) : (
            <div className={styles.emptyWrap}>
              <Empty description="Khách hàng chưa có hồ sơ nào" />
            </div>
          ))}

        {/* --- So sánh --- */}
        {view === 'compare' && (
          <>
            <div className={styles.backRow}>
              <Button
                type="text"
                size="small"
                icon={<ArrowLeftOutlined />}
                onClick={() => setView('grid')}
              >
                Quay lại
              </Button>
              <span className={styles.backTitle}>So sánh {selectedRecords.length} hồ sơ</span>
            </div>

            <div className={styles.compareScroll}>
              <table className={styles.compareTable}>
                <thead>
                  <tr>
                    <th>Chỉ tiêu</th>
                    {selectedRecords.map((r) => (
                      <th key={r.id}>{r.code}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className={styles.rowHead}>Sản phẩm</td>
                    {selectedRecords.map((r) => (
                      <td key={r.id}>{r.productName}</td>
                    ))}
                  </tr>
                  <tr>
                    <td className={styles.rowHead}>Số tiền</td>
                    {selectedRecords.map((r) => (
                      <td key={r.id}>{formatCurrency(r.amount)}</td>
                    ))}
                  </tr>
                  <tr>
                    <td className={styles.rowHead}>Thời hạn</td>
                    {selectedRecords.map((r) => (
                      <td key={r.id}>{r.termYears} năm</td>
                    ))}
                  </tr>
                  <tr>
                    <td className={styles.rowHead}>Lãi suất</td>
                    {selectedRecords.map((r) => (
                      <td key={r.id}>{formatRate(r.ratePercent)}</td>
                    ))}
                  </tr>
                  <tr>
                    <td className={styles.rowHead}>LTV</td>
                    {selectedRecords.map((r) => (
                      <td key={r.id}>{r.ltv > 0 ? `${r.ltv}%` : 'Tín chấp'}</td>
                    ))}
                  </tr>
                  <tr>
                    <td className={styles.rowHead}>Trạng thái</td>
                    {selectedRecords.map((r) => (
                      <td key={r.id}>
                        <Tag color={LOAN_STATUS_COLOR[r.status]}>{LOAN_STATUS_LABEL[r.status]}</Tag>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* --- Chi tiết + phê duyệt --- */}
        {view === 'detail' && (
          <>
            <div className={styles.backRow}>
              <Button
                type="text"
                size="small"
                icon={<ArrowLeftOutlined />}
                onClick={() => setView('grid')}
              >
                Quay lại
              </Button>
              <span className={styles.backTitle}>Chi tiết {selectedRecords.length} hồ sơ</span>
            </div>

            <div className={styles.detailList}>
              {selectedRecords.map((record) => (
                <LoanApprovalCard
                  key={record.id}
                  application={record}
                  onDecision={(status, note) => onLoanDecision(record, status, note)}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}
