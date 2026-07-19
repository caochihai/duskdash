import { useState } from 'react';
import { Alert, Button, Card, Divider, Form, Input, Typography } from 'antd';
import {
  AuditOutlined,
  DeploymentUnitOutlined,
  FileSearchOutlined,
  LockOutlined,
  LoginOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { AnimatedSHBLogo } from '@/components/common/AnimatedSHBLogo';
import { SHBAmbientBackground } from '@/features/chat/components/SHBAmbientBackground';
import { isAuthenticated, login } from '@/auth/keycloak';
import { signIn } from '@/auth/demoSession';
import { DEMO_ACCOUNT_HINTS } from '@/auth/demoAccounts';
import { USE_MOCK_API } from '@/services/apiClient';
import styles from './LoginPage.module.css';

/** Chỉ chấp nhận đường dẫn nội bộ để tránh open redirect. */
function sanitizeReturnTo(raw: string | null): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return '/';
  return raw;
}

interface LoginFormValues {
  username: string;
  password: string;
}

const CAPABILITIES = [
  {
    icon: <DeploymentUnitOutlined />,
    title: 'Hệ chuyên gia số chạy song song',
    text: 'Tín dụng, Pháp lý và Hồ sơ cùng thẩm định một bộ hồ sơ, rồi hợp nhất thành một kết luận.',
  },
  {
    icon: <FileSearchOutlined />,
    title: 'Trích dẫn về đúng vị trí trong hồ sơ',
    text: 'Mỗi luận điểm dẫn ngược về dòng và toạ độ trên tài liệu gốc để chuyên viên đối chiếu.',
  },
  {
    icon: <SafetyCertificateOutlined />,
    title: 'Chỉ thấy khách hàng được phân công',
    text: 'Phạm vi dữ liệu bám theo quyền của từng chuyên viên, áp dụng ngay ở tầng truy vấn.',
  },
  {
    icon: <AuditOutlined />,
    title: 'Quyết định vẫn thuộc về con người',
    text: 'Hệ thống đề xuất và giải trình; chuyên viên phê duyệt và mọi thao tác đều được ghi vết.',
  },
];

/** Trang đăng nhập — cửa ngõ duy nhất vào hệ thống, giữ nhận diện SHB. */
export default function LoginPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form] = Form.useForm<LoginFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prefersReducedMotion = useReducedMotion();
  const returnTo = sanitizeReturnTo(searchParams.get('returnTo'));

  if (isAuthenticated()) {
    return <Navigate to={returnTo} replace />;
  }

  /** Chế độ demo: xác thực tại chỗ. Chế độ thật: chuyển hướng sang Keycloak. */
  async function handleSubmit(values: LoginFormValues) {
    setSubmitting(true);
    setError(null);

    try {
      if (!USE_MOCK_API) {
        await login(returnTo);
        return;
      }

      // Độ trễ ngắn để trạng thái loading của nút hiện rõ trong lúc demo.
      await new Promise((resolve) => setTimeout(resolve, 320));

      const session = signIn(values.username, values.password);
      if (!session) {
        setError('Tên đăng nhập hoặc mật khẩu không đúng.');
        return;
      }

      navigate(returnTo, { replace: true });
    } finally {
      setSubmitting(false);
    }
  }

  function fillDemoAccount(username: string, password: string) {
    form.setFieldsValue({ username, password });
    setError(null);
  }

  return (
    <div className={styles.page}>
      <SHBAmbientBackground />

      <section className={styles.brandPane}>
        <AnimatedSHBLogo size="large" glow glowIntensity="subtle" />

        <h2 className={styles.brandHeading}>
          Hệ chuyên gia số hỗ trợ thẩm định tín dụng
        </h2>
        <p className={styles.brandLead}>
          Không gian làm việc dành cho cán bộ SHB: tra cứu hồ sơ khách hàng, thẩm định
          khoản vay và tra ngược mọi kết luận về đúng chứng từ gốc.
        </p>

        <ul className={styles.capabilityList}>
          {CAPABILITIES.map((item) => (
            <li key={item.title} className={styles.capability}>
              <span className={styles.capabilityIcon} aria-hidden="true">
                {item.icon}
              </span>
              <span>
                <span className={styles.capabilityTitle}>{item.title}</span>
                <span className={styles.capabilityText}>{item.text}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.formPane}>
        <motion.div
          className={styles.formCard}
          initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        >
          <Card style={{ borderRadius: 16 }} styles={{ body: { padding: 32 } }}>
            <div className={styles.formHeader}>
              <AnimatedSHBLogo size="medium" />
              <h1 className={styles.formTitle}>Đăng nhập hệ thống</h1>
              <p className={styles.formSubtitle}>
                Sử dụng tài khoản nội bộ SHB được cấp cho bạn.
              </p>
            </div>

            {error && (
              <Alert
                type="error"
                showIcon
                message={error}
                style={{ marginBottom: 16 }}
                closable
                onClose={() => setError(null)}
              />
            )}

            <Form
              form={form}
              layout="vertical"
              requiredMark={false}
              onFinish={(values) => void handleSubmit(values)}
              disabled={submitting}
            >
              <Form.Item
                name="username"
                label="Tên đăng nhập"
                rules={[{ required: true, message: 'Vui lòng nhập tên đăng nhập.' }]}
              >
                <Input
                  size="large"
                  autoComplete="username"
                  autoFocus
                  prefix={<UserOutlined />}
                  placeholder="chuyenvien1"
                />
              </Form.Item>

              <Form.Item
                name="password"
                label="Mật khẩu"
                rules={[{ required: true, message: 'Vui lòng nhập mật khẩu.' }]}
              >
                <Input.Password
                  size="large"
                  autoComplete="current-password"
                  prefix={<LockOutlined />}
                  placeholder="••••••••"
                />
              </Form.Item>

              <Button
                type="primary"
                size="large"
                block
                htmlType="submit"
                icon={<LoginOutlined />}
                loading={submitting}
              >
                Đăng nhập
              </Button>
            </Form>

            {USE_MOCK_API && (
              <div className={styles.demoSection}>
                <Divider style={{ margin: '20px 0 16px' }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    Tài khoản dùng cho bản demo
                  </Typography.Text>
                </Divider>

                <div className={styles.demoAccounts}>
                  {DEMO_ACCOUNT_HINTS.map((account) => (
                    <button
                      key={account.username}
                      type="button"
                      className={styles.demoAccount}
                      onClick={() => fillDemoAccount(account.username, account.password)}
                    >
                      <span className={styles.demoAccountName}>{account.displayName}</span>
                      <span className={styles.demoAccountCredential}>
                        {account.username} / {account.password}
                      </span>
                      <span className={styles.demoAccountMeta}>
                        {account.department} · {account.branch} · được phân công{' '}
                        {account.customerCount} khách hàng
                      </span>
                    </button>
                  ))}
                </div>

                <Typography.Paragraph
                  type="secondary"
                  style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}
                >
                  Bấm vào một tài khoản để điền sẵn thông tin. Hai tài khoản được phân
                  công danh mục khách hàng khác nhau — đăng nhập chéo để thấy phạm vi dữ
                  liệu thay đổi theo quyền.
                </Typography.Paragraph>
              </div>
            )}
          </Card>
        </motion.div>
      </section>
    </div>
  );
}
