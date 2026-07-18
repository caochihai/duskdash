import { Button, Checkbox, Tag, Tooltip } from 'antd';
import {
  AuditOutlined,
  DiffOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';
import { formatCurrency } from '@/utils/formatCurrency';
import { formatDate } from '@/utils/formatDate';
import { LOAN_STATUS_COLOR, LOAN_STATUS_LABEL, type LoanApplication } from '@/types/customer';
import styles from './CustomerRecordGrid.module.css';

export interface CustomerRecordGridProps {
  records: LoanApplication[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onToggleAll: (select: boolean) => void;
  /** Đưa các hồ sơ đã chọn vào chat cho hệ chuyên gia số thẩm định. */
  onReviewSelected: () => void;
  /** Mở chi tiết từng hồ sơ đã chọn. */
  onOpenSelected: () => void;
  /** So sánh các hồ sơ đã chọn. */
  onCompareSelected: () => void;
}

/**
 * Lưới file hồ sơ của khách hàng, cho phép chọn nhiều.
 *
 * Sau khi chọn, chuyên viên có 3 lựa chọn: đưa vào chat để thẩm định,
 * mở chi tiết, hoặc so sánh cạnh nhau.
 */
export function CustomerRecordGrid({
  records,
  selectedIds,
  onToggle,
  onToggleAll,
  onReviewSelected,
  onOpenSelected,
  onCompareSelected,
}: CustomerRecordGridProps) {
  const selectedCount = selectedIds.length;
  const allSelected = records.length > 0 && selectedCount === records.length;

  return (
    <div>
      <div className={styles.selectAllRow}>
        <span className={styles.selectAllLabel}>{records.length} hồ sơ liên quan</span>
        <Checkbox
          checked={allSelected}
          indeterminate={selectedCount > 0 && !allSelected}
          onChange={(e) => onToggleAll(e.target.checked)}
        >
          Chọn tất cả
        </Checkbox>
      </div>

      <div className={styles.grid} role="group" aria-label="Danh sách hồ sơ khách hàng">
        {records.map((record) => {
          const selected = selectedIds.includes(record.id);
          return (
            <div
              key={record.id}
              className={[styles.card, selected ? styles.cardSelected : '']
                .filter(Boolean)
                .join(' ')}
              role="checkbox"
              aria-checked={selected}
              tabIndex={0}
              onClick={() => onToggle(record.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onToggle(record.id);
                }
              }}
            >
              <div className={styles.top}>
                <span className={styles.fileIcon} aria-hidden="true">
                  <FileTextOutlined />
                </span>
                <Checkbox
                  className={styles.check}
                  checked={selected}
                  // Click ô check cũng do card xử lý -> chặn double toggle.
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => onToggle(record.id)}
                  aria-label={`Chọn hồ sơ ${record.code}`}
                />
              </div>

              <span className={styles.code}>{record.code}</span>
              <span className={styles.product}>{record.productName}</span>
              <span className={styles.amount}>{formatCurrency(record.amount)}</span>

              <div className={styles.metaRow}>
                <Tag color={LOAN_STATUS_COLOR[record.status]} style={{ marginInlineEnd: 0 }}>
                  {LOAN_STATUS_LABEL[record.status]}
                </Tag>
                <span className={styles.date}>{formatDate(record.submittedAt)}</span>
              </div>
            </div>
          );
        })}
      </div>

      {selectedCount > 0 && (
        <div className={styles.actionBar} role="toolbar" aria-label="Thao tác với hồ sơ đã chọn">
          <span className={styles.actionCount}>Đã chọn {selectedCount} hồ sơ</span>

          <Button type="primary" icon={<AuditOutlined />} onClick={onReviewSelected}>
            Thẩm định
          </Button>

          <Tooltip title={selectedCount < 2 ? 'Chọn từ 2 hồ sơ để so sánh' : undefined}>
            <Button
              icon={<DiffOutlined />}
              onClick={onCompareSelected}
              disabled={selectedCount < 2}
            >
              So sánh
            </Button>
          </Tooltip>

          <Button icon={<FolderOpenOutlined />} onClick={onOpenSelected}>
            Mở
          </Button>
        </div>
      )}
    </div>
  );
}
