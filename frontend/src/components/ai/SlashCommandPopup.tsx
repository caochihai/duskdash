import { useEffect, useRef } from 'react';
import { Avatar, Tag } from 'antd';
import { ShopOutlined, UserOutlined } from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { formatCurrency } from '@/utils/formatCurrency';
import { shbColors } from '@/theme/tokens';
import { RISK_LABEL, type Customer } from '@/types/customer';
import styles from './SlashCommandPopup.module.css';

export interface SlashCommandPopupProps {
  customers: Customer[];
  activeIndex: number;
  onHover: (index: number) => void;
  onSelect: (customer: Customer) => void;
}

const RISK_COLOR: Record<Customer['riskLevel'], string> = {
  low: 'green',
  medium: 'gold',
  high: 'red',
};

/**
 * Popup chọn khách hàng khi chuyên viên gõ `/` trong composer.
 *
 * Điều hướng bằng bàn phím (↑ ↓ Enter Esc) do `ChatComposer` xử lý, vì phím
 * phải được chặn ngay trên textarea của Sender trước khi nó gửi tin nhắn.
 */
export function SlashCommandPopup({
  customers,
  activeIndex,
  onHover,
  onSelect,
}: SlashCommandPopupProps) {
  const prefersReducedMotion = useReducedMotion();
  const listRef = useRef<HTMLDivElement>(null);

  // Luôn giữ mục đang chọn trong tầm nhìn khi dùng phím mũi tên.
  useEffect(() => {
    const active = listRef.current?.querySelector('[data-active="true"]');
    active?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  return (
    <motion.div
      ref={listRef}
      className={styles.popup}
      role="listbox"
      aria-label="Chọn khách hàng"
      initial={prefersReducedMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={styles.hint}>
        <span>Chọn khách hàng để tra cứu</span>
        <span className={styles.kbd}>
          <kbd className={styles.key}>↑</kbd>
          <kbd className={styles.key}>↓</kbd>
          <kbd className={styles.key}>Enter</kbd>
          <kbd className={styles.key}>Esc</kbd>
        </span>
      </div>

      {customers.length === 0 ? (
        <div className={styles.empty}>Không tìm thấy khách hàng phù hợp</div>
      ) : (
        customers.map((customer, index) => (
          <button
            key={customer.id}
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            data-active={index === activeIndex}
            className={[styles.item, index === activeIndex ? styles.itemActive : '']
              .filter(Boolean)
              .join(' ')}
            onMouseEnter={() => onHover(index)}
            // onMouseDown thay vì onClick: chạy trước khi textarea mất focus.
            onMouseDown={(event) => {
              event.preventDefault();
              onSelect(customer);
            }}
          >
            <Avatar
              className={styles.avatar}
              size={30}
              icon={customer.segment === 'business' ? <ShopOutlined /> : <UserOutlined />}
              style={{ background: shbColors.navy[100], color: shbColors.navy[700] }}
            />

            <span className={styles.body}>
              <span className={styles.name}>{customer.fullName}</span>
              <span className={styles.meta}>
                {customer.code} • {customer.branch} • Dư nợ {formatCurrency(customer.existingDebt)}
              </span>
            </span>

            <span className={styles.right}>
              <Tag color={RISK_COLOR[customer.riskLevel]} bordered={false}>
                {RISK_LABEL[customer.riskLevel]}
              </Tag>
            </span>
          </button>
        ))
      )}
    </motion.div>
  );
}
