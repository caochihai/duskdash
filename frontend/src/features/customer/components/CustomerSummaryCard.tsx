import { Avatar, Button, Tag } from 'antd';
import { ShopOutlined, UserOutlined } from '@ant-design/icons';
import { formatCurrency } from '@/utils/formatCurrency';
import { shbColors } from '@/theme/tokens';
import { RISK_LABEL, type Customer } from '@/types/customer';
import styles from './CustomerSummaryCard.module.css';

export interface CustomerSummaryCardProps {
  customer: Customer;
  onViewDetail?: (customerId: string) => void;
}

const RISK_COLOR: Record<Customer['riskLevel'], string> = {
  low: 'green',
  medium: 'gold',
  high: 'red',
};

/** Tóm tắt khách hàng hiển thị ngay trong luồng hội thoại. */
export function CustomerSummaryCard({ customer, onViewDetail }: CustomerSummaryCardProps) {
  return (
    <section className={styles.card} aria-label={`Tóm tắt khách hàng ${customer.fullName}`}>
      <Avatar
        size={40}
        icon={customer.segment === 'business' ? <ShopOutlined /> : <UserOutlined />}
        style={{ background: shbColors.navy[100], color: shbColors.navy[700], flexShrink: 0 }}
      />

      <div className={styles.body}>
        <div className={styles.nameRow}>
          <span className={styles.name}>{customer.fullName}</span>
          <Tag color={RISK_COLOR[customer.riskLevel]} bordered={false}>
            {RISK_LABEL[customer.riskLevel]}
          </Tag>
        </div>
        <span className={styles.meta}>
          {customer.code} • {customer.branch}
        </span>

        <div className={styles.stats}>
          <span className={styles.stat}>
            <span className={styles.statLabel}>Điểm tín dụng</span>
            <span className={styles.statValue}>{customer.creditScore}</span>
          </span>
          <span className={styles.stat}>
            <span className={styles.statLabel}>DTI</span>
            <span className={styles.statValue}>{customer.dti}%</span>
          </span>
          <span className={styles.stat}>
            <span className={styles.statLabel}>Dư nợ</span>
            <span className={styles.statValue}>{formatCurrency(customer.existingDebt)}</span>
          </span>
        </div>
      </div>

      {onViewDetail && (
        <Button size="small" onClick={() => onViewDetail(customer.id)}>
          Xem hồ sơ
        </Button>
      )}
    </section>
  );
}
