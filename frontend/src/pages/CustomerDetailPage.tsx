import { useMemo, useState } from 'react';
import { App, Avatar, Button, Card, Empty, Modal, Tabs, Tag, Timeline } from 'antd';
import {
  ArrowLeftOutlined,
  AuditOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  LockOutlined,
  MessageOutlined,
  ShopOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { SHBLogo } from '@/components/common/SHBLogo';
import { LoanApprovalCard } from '@/features/customer/components/LoanApprovalCard';
import { formatCurrency, formatRate } from '@/utils/formatCurrency';
import { formatDate } from '@/utils/formatDate';
import { shbColors } from '@/theme/tokens';
import {
  findCustomerById,
  findLoansByCustomer,
} from '@/features/chat/constants/mockCustomers';
import {
  LOAN_STATUS_COLOR,
  LOAN_STATUS_LABEL,
  RISK_LABEL,
  SEGMENT_LABEL,
  type Customer,
  type LoanApplication,
  type LoanApplicationStatus,
} from '@/types/customer';
import styles from './CustomerDetailPage.module.css';

const RISK_COLOR: Record<Customer['riskLevel'], string> = {
  low: 'green',
  medium: 'gold',
  high: 'red',
};

function dtiColor(dti: number): string {
  if (dti >= 50) return shbColors.semantic.error;
  if (dti >= 40) return shbColors.semantic.warning;
  return shbColors.semantic.success;
}

/**
 * Trang hồ sơ khách hàng — "một section riêng cho mỗi người".
 *
 * Route: /customer/:id
 * Tabs: Tổng quan · Hồ sơ vay (tất cả) · Lịch sử
 * Chuyên viên xem toàn bộ hồ sơ của khách hàng và thao tác thẩm định/phê duyệt
 * ngay tại đây.
 */
export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message: messageApi } = App.useApp();
  const prefersReducedMotion = useReducedMotion();

  const [tab, setTab] = useState('overview');
  const [reviewLoan, setReviewLoan] = useState<LoanApplication | null>(null);

  const customer = id ? findCustomerById(id) : undefined;
  const loans = useMemo(() => (id ? findLoansByCustomer(id) : []), [id]);

  const pendingLoans = loans.filter((l) => l.status === 'pending' || l.status === 'need-info');
  const historyLoans = loans.filter(
    (l) => l.status === 'approved' || l.status === 'rejected' || l.status === 'closed',
  );

  // Không tìm thấy khách hàng.
  if (!customer) {
    return (
      <div className={styles.page}>
        <header className={styles.header}>
          <SHBLogo size="small" showProductName />
          <Link to="/">
            <Button icon={<ArrowLeftOutlined />}>Về giao diện trò chuyện</Button>
          </Link>
        </header>
        <div className={styles.container}>
          <Empty description="Không tìm thấy khách hàng" style={{ paddingTop: 60 }}>
            <Button type="primary" onClick={() => navigate('/')}>
              Quay lại
            </Button>
          </Empty>
        </div>
      </div>
    );
  }

  const handleDecision = (
    application: LoanApplication,
    status: LoanApplicationStatus,
    note: string,
  ) => {
    messageApi.success(
      `${LOAN_STATUS_LABEL[status]}: ${application.code}${note ? ` — ${note}` : ''}`,
    );
  };

  /* ---------------- Tab: Tổng quan ---------------- */

  const overviewTab = (
    <Card size="small" title="Hồ sơ tín dụng">
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

      <div style={{ marginTop: 16 }}>
        <div className={styles.meter} aria-hidden="true">
          <div
            className={styles.meterFill}
            style={{ width: `${Math.min(customer.dti, 100)}%`, background: dtiColor(customer.dti) }}
          />
        </div>
        <div className={styles.meterNote}>
          <span>Tỷ lệ nợ trên thu nhập (DTI): {customer.dti}%</span>
          <span>Ngưỡng chính sách 50%</span>
        </div>
      </div>

      <p className={styles.maskNote}>
        <LockOutlined className={styles.maskIcon} aria-hidden="true" />
        <span>
          Thông tin định danh được che theo nguyên tắc tối thiểu hoá dữ liệu. Xem đầy đủ cần quyền
          truy cập riêng và sẽ được ghi vết kiểm toán.
        </span>
      </p>
    </Card>
  );

  /* ---------------- Tab: Hồ sơ vay ---------------- */

  const renderLoanCard = (loan: LoanApplication, index: number) => (
    <motion.div
      key={loan.id}
      className={styles.loanCard}
      initial={prefersReducedMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: index * 0.04, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={styles.loanMain}>
        <div className={styles.loanTop}>
          <span className={styles.loanCode}>{loan.code}</span>
          <Tag color={LOAN_STATUS_COLOR[loan.status]}>{LOAN_STATUS_LABEL[loan.status]}</Tag>
        </div>
        <span className={styles.loanProduct}>{loan.productName}</span>
        <span className={styles.loanMeta}>
          {loan.termYears} năm • {formatRate(loan.ratePercent)} •{' '}
          {loan.ltv > 0 ? `LTV ${loan.ltv}%` : 'Tín chấp'} • Nộp {formatDate(loan.submittedAt)}
        </span>
      </div>

      <div className={styles.loanAmount}>
        <span className={styles.loanAmountValue}>{formatCurrency(loan.amount)}</span>
        <span className={styles.loanAmountLabel}>{loan.purpose}</span>
      </div>

      <div className={styles.loanAction}>
        {loan.status === 'pending' || loan.status === 'need-info' ? (
          <Button type="primary" icon={<AuditOutlined />} onClick={() => setReviewLoan(loan)}>
            Thẩm định
          </Button>
        ) : (
          <Button icon={<FileTextOutlined />} onClick={() => setReviewLoan(loan)}>
            Xem chi tiết
          </Button>
        )}
      </div>
    </motion.div>
  );

  const loansTab = loans.length ? (
    <div className={styles.loanList}>{loans.map(renderLoanCard)}</div>
  ) : (
    <div className={styles.emptyWrap}>
      <Empty description="Khách hàng chưa có hồ sơ vay nào" />
    </div>
  );

  /* ---------------- Tab: Lịch sử ---------------- */

  const historyTab = historyLoans.length ? (
    <Card size="small">
      <Timeline
        items={historyLoans.map((loan) => ({
          color:
            loan.status === 'approved'
              ? 'green'
              : loan.status === 'rejected'
                ? 'red'
                : 'gray',
          children: (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <strong style={{ color: 'var(--shb-navy-800)' }}>{loan.code}</strong>
                <Tag color={LOAN_STATUS_COLOR[loan.status]}>{LOAN_STATUS_LABEL[loan.status]}</Tag>
              </span>
              <span style={{ fontSize: 13.5, color: 'var(--shb-navy-700)' }}>
                {loan.productName} — {formatCurrency(loan.amount)}
              </span>
              <span style={{ fontSize: 12, color: 'var(--shb-text-muted)' }}>
                Nộp {formatDate(loan.submittedAt)}
              </span>
            </div>
          ),
        }))}
      />
    </Card>
  ) : (
    <div className={styles.emptyWrap}>
      <Empty description="Chưa có lịch sử hồ sơ đã xử lý" />
    </div>
  );

  /* ---------------- Render ---------------- */

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <SHBLogo size="small" showProductName />
        <Link to="/">
          <Button icon={<ArrowLeftOutlined />}>Về giao diện trò chuyện</Button>
        </Link>
      </header>

      <div className={styles.container}>
        <div className={styles.identity}>
          <Avatar
            size={60}
            icon={customer.segment === 'business' ? <ShopOutlined /> : <UserOutlined />}
            style={{ background: shbColors.navy[100], color: shbColors.navy[700], flexShrink: 0 }}
          />
          <div className={styles.identityBody}>
            {/* h1 duy nhất của trang */}
            <h1 className={styles.name}>{customer.fullName}</h1>
            <span className={styles.code}>{customer.code}</span>
            <div className={styles.tags}>
              <Tag color={RISK_COLOR[customer.riskLevel]}>{RISK_LABEL[customer.riskLevel]}</Tag>
              <Tag>{SEGMENT_LABEL[customer.segment]}</Tag>
              <Tag>{customer.branch}</Tag>
            </div>
          </div>

          <div className={styles.identityStats}>
            <span className={styles.stat}>
              <span className={styles.statLabel}>Hồ sơ chờ xử lý</span>
              <span className={styles.statValue}>{pendingLoans.length}</span>
            </span>
            <span className={styles.stat}>
              <span className={styles.statLabel}>Tổng hồ sơ</span>
              <span className={styles.statValue}>{loans.length}</span>
            </span>
            <span className={styles.stat}>
              <span className={styles.statLabel}>Điểm tín dụng</span>
              <span className={styles.statValue}>{customer.creditScore}</span>
            </span>
          </div>
        </div>

        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            {
              key: 'overview',
              label: (
                <span>
                  <UserOutlined /> Tổng quan
                </span>
              ),
              children: overviewTab,
            },
            {
              key: 'loans',
              label: (
                <span>
                  <FileTextOutlined /> Hồ sơ vay ({loans.length})
                </span>
              ),
              children: loansTab,
            },
            {
              key: 'history',
              label: (
                <span>
                  <ClockCircleOutlined /> Lịch sử ({historyLoans.length})
                </span>
              ),
              children: historyTab,
            },
          ]}
        />
      </div>

      {/* Thẩm định / phê duyệt hồ sơ ngay trong section này. */}
      <Modal
        open={reviewLoan !== null}
        onCancel={() => setReviewLoan(null)}
        footer={null}
        width={640}
        destroyOnHidden
        title={reviewLoan ? `Thẩm định hồ sơ ${reviewLoan.code}` : ''}
      >
        {reviewLoan && (
          <LoanApprovalCard
            application={reviewLoan}
            onDecision={(status, note) => {
              handleDecision(reviewLoan, status, note);
            }}
          />
        )}
      </Modal>

      {/* Nút quay lại chat để hỏi agent về khách hàng này. */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px' }}>
        <Button
          type="link"
          icon={<MessageOutlined />}
          onClick={() =>
            navigate('/', { state: { askCustomer: { id: customer.id, name: customer.fullName } } })
          }
        >
          Hỏi hệ chuyên gia số về khách hàng này
        </Button>
      </div>
    </div>
  );
}
