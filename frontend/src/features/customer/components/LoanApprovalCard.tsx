import { useState } from 'react';
import { App, Alert, Button, Input, Modal, Popconfirm, Tag, Tooltip } from 'antd';
import {
  CheckCircleFilled,
  CheckOutlined,
  CloseCircleFilled,
  CloseOutlined,
  ExclamationCircleFilled,
  FileSearchOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { formatCurrency, formatRate } from '@/utils/formatCurrency';
import { formatDateTime } from '@/utils/formatDate';
import { AGENT_SHORT_LABEL } from '@/types/agent';
import {
  LOAN_STATUS_COLOR,
  LOAN_STATUS_LABEL,
  type LoanApplication,
  type LoanApplicationStatus,
} from '@/types/customer';
import styles from './LoanApprovalCard.module.css';

export interface LoanApprovalCardProps {
  application: LoanApplication;
  onDecision?: (status: LoanApplicationStatus, note: string) => void;
  onViewCustomer?: (customerId: string) => void;
}


/**
 * Thẻ phê duyệt khoản vay — hành động nghiệp vụ chính của chuyên viên tín dụng.
 *
 * Nguyên tắc an toàn áp dụng ở đây:
 * - Quyết định luôn cần xác nhận hai bước (Popconfirm / Modal), không bấm nhầm là duyệt.
 * - Vượt hạn mức phê duyệt của chuyên viên -> KHOÁ nút duyệt, buộc trình cấp cao hơn.
 * - Có chốt kiểm tra không đạt -> cảnh báo rõ trước khi duyệt.
 * - Từ chối bắt buộc nhập lý do (yêu cầu kiểm toán).
 */
export function LoanApprovalCard({ application, onDecision, onViewCustomer }: LoanApprovalCardProps) {
  const { modal } = App.useApp();
  const [status, setStatus] = useState<LoanApplicationStatus>(application.status);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const failedChecks = application.checks.filter((check) => !check.passed);
  const hasFailures = failedChecks.length > 0;
  const overLimit = application.amount > application.approvalLimit;
  const decided = status !== 'pending';

  const applyDecision = (next: LoanApplicationStatus, note: string) => {
    setStatus(next);
    onDecision?.(next, note);
  };

  const handleApprove = () => {
    // Có chốt kiểm tra không đạt -> bắt xác nhận lần nữa, nêu rõ rủi ro.
    if (hasFailures) {
      modal.confirm({
        title: 'Hồ sơ có chốt kiểm tra không đạt',
        icon: <ExclamationCircleFilled style={{ color: '#D97706' }} />,
        content: (
          <div>
            <p style={{ marginTop: 0 }}>
              {failedChecks.length} chốt kiểm tra chưa đạt. Việc phê duyệt sẽ được ghi nhận là
              <strong> phê duyệt ngoại lệ</strong> và lưu vết kiểm toán.
            </p>
            <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
              {failedChecks.map((check) => (
                <li key={check.label}>{check.label}</li>
              ))}
            </ul>
          </div>
        ),
        okText: 'Vẫn phê duyệt',
        okButtonProps: { danger: true },
        cancelText: 'Huỷ',
        onOk: () => applyDecision('approved', 'Phê duyệt ngoại lệ'),
      });
      return;
    }
    applyDecision('approved', 'Phê duyệt theo đề xuất của hệ chuyên gia số');
  };

  const confirmReject = () => {
    if (!rejectReason.trim()) return;
    applyDecision('rejected', rejectReason.trim());
    setRejectOpen(false);
  };

  return (
    <section className={styles.card} aria-label={`Hồ sơ vay ${application.code}`}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.code}>{application.code}</span>
          <h3 className={styles.title}>{application.productName}</h3>
          <span className={styles.customer}>
            {application.customerName} • Nộp lúc {formatDateTime(application.submittedAt)}
          </span>
        </div>
        <Tag color={LOAN_STATUS_COLOR[status]}>{LOAN_STATUS_LABEL[status]}</Tag>
      </div>

      <div className={styles.grid}>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Số tiền đề nghị</span>
          <span className={styles.itemValue}>{formatCurrency(application.amount)}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Thời hạn</span>
          <span className={styles.itemValue}>{application.termYears} năm</span>
        </div>
        <div className={styles.item}>
          <span className={styles.itemLabel}>Lãi suất</span>
          <span className={styles.itemValue}>{formatRate(application.ratePercent)}</span>
        </div>
        <div className={styles.item}>
          <span className={styles.itemLabel}>LTV</span>
          <span className={styles.itemValue}>
            {application.ltv > 0 ? `${application.ltv}%` : 'Tín chấp'}
          </span>
        </div>
      </div>

      <div className={styles.checks}>
        <h4 className={styles.checksTitle}>
          Kết quả thẩm định của các chuyên gia số ({application.checks.length - failedChecks.length}/
          {application.checks.length} đạt)
        </h4>

        <ul className={styles.checkList}>
          {application.checks.map((check) => (
            <li key={check.label} className={styles.check}>
              {check.passed ? (
                <CheckCircleFilled
                  className={[styles.checkIcon, styles.checkPass].join(' ')}
                  aria-hidden="true"
                />
              ) : (
                <CloseCircleFilled
                  className={[styles.checkIcon, styles.checkFail].join(' ')}
                  aria-hidden="true"
                />
              )}
              <span className={styles.checkBody}>
                <span className={styles.checkLabel}>
                  <Tag bordered={false} color={check.passed ? 'default' : 'red'}>
                    {AGENT_SHORT_LABEL[check.agent]}
                  </Tag>
                  {check.label}
                  {/* Không chỉ dùng màu làm tín hiệu — luôn kèm nhãn chữ. */}
                  <span className="sr-only">{check.passed ? ' — Đạt' : ' — Không đạt'}</span>
                </span>
                <span className={styles.checkNote}>{check.note}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      {overLimit && !decided && (
        <div style={{ padding: '0 18px 12px' }}>
          <Alert
            type="warning"
            showIcon
            message="Vượt hạn mức phê duyệt của bạn"
            description={`Số tiền ${formatCurrency(application.amount)} vượt hạn mức ${formatCurrency(application.approvalLimit)}. Hồ sơ phải trình cấp phê duyệt cao hơn.`}
          />
        </div>
      )}

      {decided ? (
        <div
          className={[
            styles.decided,
            status === 'approved'
              ? styles.decidedApproved
              : status === 'rejected'
                ? styles.decidedRejected
                : styles.decidedInfo,
          ].join(' ')}
        >
          {status === 'approved' && <CheckCircleFilled aria-hidden="true" />}
          {status === 'rejected' && <CloseCircleFilled aria-hidden="true" />}
          {status === 'need-info' && <ExclamationCircleFilled aria-hidden="true" />}
          {LOAN_STATUS_LABEL[status]} — đã ghi nhận trong phiên demo, chưa gửi tới hệ thống thật.
        </div>
      ) : (
        <div className={styles.actions}>
          <Tooltip title={overLimit ? 'Vượt hạn mức phê duyệt của bạn' : undefined}>
            <Popconfirm
              title="Phê duyệt khoản vay?"
              description={`${application.code} — ${formatCurrency(application.amount)}`}
              okText="Phê duyệt"
              cancelText="Huỷ"
              disabled={overLimit}
              onConfirm={handleApprove}
            >
              <Button type="primary" icon={<CheckOutlined />} disabled={overLimit}>
                Phê duyệt khoản vay
              </Button>
            </Popconfirm>
          </Tooltip>

          <Button danger icon={<CloseOutlined />} onClick={() => setRejectOpen(true)}>
            Từ chối
          </Button>

          <Button
            icon={<FileSearchOutlined />}
            onClick={() => applyDecision('need-info', 'Yêu cầu bổ sung hồ sơ')}
          >
            Yêu cầu bổ sung
          </Button>

          {onViewCustomer && (
            <Button
              type="text"
              icon={<UserOutlined />}
              onClick={() => onViewCustomer(application.customerId)}
            >
              Xem hồ sơ khách hàng
            </Button>
          )}

          <span className={styles.spacer} />
          <span className={styles.limitNote}>
            Hạn mức của bạn: {formatCurrency(application.approvalLimit)}
          </span>
        </div>
      )}

      <Modal
        open={rejectOpen}
        title="Từ chối hồ sơ vay"
        okText="Xác nhận từ chối"
        cancelText="Huỷ"
        okButtonProps={{ danger: true, disabled: !rejectReason.trim() }}
        onOk={confirmReject}
        onCancel={() => setRejectOpen(false)}
        destroyOnHidden
      >
        <p style={{ marginTop: 0, color: 'var(--shb-text-secondary)' }}>
          Lý do từ chối sẽ được lưu vết kiểm toán và dùng để thông báo cho khách hàng.
        </p>
        <Input.TextArea
          value={rejectReason}
          onChange={(event) => setRejectReason(event.target.value)}
          placeholder="Nhập lý do từ chối (bắt buộc)"
          rows={3}
          maxLength={300}
          showCount
          aria-label="Lý do từ chối"
        />
      </Modal>
    </section>
  );
}
