import { Button, Tag } from 'antd';
import { SlidersOutlined } from '@ant-design/icons';
import { formatCurrency, formatRate } from '@/utils/formatCurrency';
import type { LoanEstimateBlock } from '@/types/chat';
import styles from './LoanEstimateCard.module.css';

export interface LoanEstimateCardProps {
  estimate: LoanEstimateBlock;
  onAdjust?: () => void;
}

/**
 * Thẻ ước tính khoản vay.
 *
 * Con số được tính ở phía demo (xem `loanCalculator.ts`) và luôn được gắn nhãn
 * "Dữ liệu demo" — đây không phải báo giá tín dụng chính thức.
 */
export function LoanEstimateCard({ estimate, onAdjust }: LoanEstimateCardProps) {
  return (
    <section className={styles.card} aria-label="Ước tính khoản vay">
      <div className={styles.badgeRow}>
        <Tag color="orange">Ước tính</Tag>
        <Tag>Dữ liệu demo</Tag>
      </div>

      <div className={styles.headline}>
        <span className={styles.headlineLabel}>Khoản thanh toán hàng tháng ước tính</span>
        <span className={styles.headlineValue}>
          {formatCurrency(estimate.monthlyPayment)}
          <span className={styles.headlineUnit}> /tháng</span>
        </span>
      </div>

      <div className={styles.grid}>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Số tiền vay</span>
          <span className={styles.itemValue}>{formatCurrency(estimate.amount)}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Thời hạn</span>
          <span className={styles.itemValue}>{estimate.termYears} năm</span>
        </div>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Lãi suất giả định</span>
          <span className={styles.itemValue}>{formatRate(estimate.assumedRatePercent)}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Phương thức</span>
          <span className={styles.itemValue}>{estimate.method}</span>
        </div>
      </div>

      <div className={styles.footer}>
        <span className={styles.note}>
          Tổng tiền lãi dự kiến {formatCurrency(estimate.totalInterest)} • Tổng thanh toán{' '}
          {formatCurrency(estimate.totalPayment)}
        </span>

        {onAdjust && (
          <Button size="small" icon={<SlidersOutlined />} onClick={onAdjust}>
            Điều chỉnh thông số
          </Button>
        )}
      </div>
    </section>
  );
}
