import { Avatar, Button, Drawer, Grid, Tag } from 'antd';
import {
  BankOutlined,
  FileTextOutlined,
  LockOutlined,
  ProfileOutlined,
  ShopOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { formatCurrency } from '@/utils/formatCurrency';
import { formatDate } from '@/utils/formatDate';
import { shbColors } from '@/theme/tokens';
import { RISK_LABEL, SEGMENT_LABEL, type Customer, type LoanApplication } from '@/types/customer';
import styles from './CustomerProfileDrawer.module.css';

export interface CustomerProfileDrawerProps {
  open: boolean;
  onClose: () => void;
  customer: Customer | null;
  /** Hồ sơ vay đang mở của khách hàng, nếu có. */
  loan?: LoanApplication;
  onReviewLoan?: (loan: LoanApplication) => void;
  onAskAbout?: (customer: Customer) => void;
  /** Mở trang hồ sơ đầy đủ (/customer/:id). */
  onOpenFullProfile?: (customer: Customer) => void;
}

const RISK_COLOR: Record<Customer['riskLevel'], string> = {
  low: 'green',
  medium: 'gold',
  high: 'red',
};

/** Màu thanh DTI theo ngưỡng chính sách (50%). */
function dtiColor(dti: number): string {
  if (dti >= 50) return shbColors.semantic.error;
  if (dti >= 40) return shbColors.semantic.warning;
  return shbColors.semantic.success;
}

/** Hồ sơ khách hàng — mở khi chuyên viên chọn khách hàng qua lệnh `/`. */
export function CustomerProfileDrawer({
  open,
  onClose,
  customer,
  loan,
  onReviewLoan,
  onAskAbout,
  onOpenFullProfile,
}: CustomerProfileDrawerProps) {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      width={isMobile ? '100%' : 400}
      destroyOnHidden
      title="Hồ sơ khách hàng"
    >
      {customer && (
        <>
          <div className={styles.identity}>
            <Avatar
              size={48}
              icon={customer.segment === 'business' ? <ShopOutlined /> : <UserOutlined />}
              style={{ background: shbColors.navy[100], color: shbColors.navy[700] }}
            />
            <div className={styles.identityBody}>
              <h3 className={styles.name}>{customer.fullName}</h3>
              <span className={styles.code}>{customer.code}</span>
              <div className={styles.tags}>
                <Tag color={RISK_COLOR[customer.riskLevel]}>{RISK_LABEL[customer.riskLevel]}</Tag>
                <Tag>{SEGMENT_LABEL[customer.segment]}</Tag>
              </div>
            </div>
          </div>

          <div className={styles.section}>
            <h4 className={styles.sectionTitle}>Thông tin định danh</h4>
            <div className={styles.rows}>
              <div className={styles.row}>
                <span className={styles.rowLabel}>
                  {customer.segment === 'business' ? 'Mã số thuế' : 'CCCD'}
                </span>
                <span className={styles.rowValue}>{customer.idNumberMasked}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.rowLabel}>Điện thoại</span>
                <span className={styles.rowValue}>{customer.phoneMasked}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.rowLabel}>Chi nhánh quản lý</span>
                <span className={styles.rowValue}>{customer.branch}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.rowLabel}>Khách hàng từ</span>
                <span className={styles.rowValue}>{formatDate(customer.customerSince)}</span>
              </div>
            </div>

            <p className={styles.maskNote}>
              <LockOutlined className={styles.maskIcon} aria-hidden="true" />
              <span>
                Thông tin định danh được che theo nguyên tắc tối thiểu hoá dữ liệu. Xem đầy đủ cần
                quyền truy cập riêng và sẽ được ghi vết kiểm toán.
              </span>
            </p>
          </div>

          <div className={styles.section}>
            <h4 className={styles.sectionTitle}>Hồ sơ tín dụng</h4>
            <div className={styles.rows}>
              <div className={styles.row}>
                <span className={styles.rowLabel}>Điểm tín dụng</span>
                <span className={styles.rowValue}>{customer.creditScore}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.rowLabel}>
                  {customer.segment === 'business' ? 'Doanh thu/tháng' : 'Thu nhập/tháng'}
                </span>
                <span className={styles.rowValue}>{formatCurrency(customer.monthlyIncome)}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.rowLabel}>Dư nợ hiện tại</span>
                <span className={styles.rowValue}>{formatCurrency(customer.existingDebt)}</span>
              </div>
            </div>

            <div>
              <div className={styles.meter} aria-hidden="true">
                <div
                  className={styles.meterFill}
                  style={{
                    width: `${Math.min(customer.dti, 100)}%`,
                    background: dtiColor(customer.dti),
                  }}
                />
              </div>
              <div className={styles.meterNote}>
                <span>DTI {customer.dti}%</span>
                <span>Ngưỡng chính sách 50%</span>
              </div>
            </div>
          </div>

          {loan && (
            <div className={styles.section}>
              <h4 className={styles.sectionTitle}>Hồ sơ vay đang mở</h4>
              <div className={styles.rows}>
                <div className={styles.row}>
                  <span className={styles.rowLabel}>{loan.code}</span>
                  <span className={styles.rowValue}>{formatCurrency(loan.amount)}</span>
                </div>
                <div className={styles.row}>
                  <span className={styles.rowLabel}>Sản phẩm</span>
                  <span className={styles.rowValue}>{loan.productName}</span>
                </div>
              </div>
            </div>
          )}

          <div className={styles.actions}>
            {onOpenFullProfile && (
              <Button
                type="primary"
                icon={<ProfileOutlined />}
                onClick={() => onOpenFullProfile(customer)}
                block
              >
                Xem trang hồ sơ đầy đủ
              </Button>
            )}
            {loan && onReviewLoan && (
              <Button icon={<FileTextOutlined />} onClick={() => onReviewLoan(loan)} block>
                Thẩm định hồ sơ vay {loan.code}
              </Button>
            )}
            {onAskAbout && (
              <Button icon={<BankOutlined />} onClick={() => onAskAbout(customer)} block>
                Hỏi hệ chuyên gia số về khách hàng này
              </Button>
            )}
          </div>
        </>
      )}
    </Drawer>
  );
}
