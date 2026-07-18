import { useState } from 'react';
import { Button, Card, Typography } from 'antd';
import { LoginOutlined } from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { AnimatedSHBLogo } from '@/components/common/AnimatedSHBLogo';
import { SHBAmbientBackground } from '@/features/chat/components/SHBAmbientBackground';
import { isAuthenticated, login } from '@/auth/keycloak';

/** Chỉ chấp nhận đường dẫn nội bộ để tránh open redirect. */
function sanitizeReturnTo(raw: string | null): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return '/';
  return raw;
}

/** Trang đăng nhập — cửa ngõ duy nhất vào hệ thống, giữ nhận diện SHB. */
export default function LoginPage() {
  const [searchParams] = useSearchParams();
  const [redirecting, setRedirecting] = useState(false);
  const prefersReducedMotion = useReducedMotion();
  const returnTo = sanitizeReturnTo(searchParams.get('returnTo'));

  if (isAuthenticated()) {
    return <Navigate to={returnTo} replace />;
  }

  async function handleLogin() {
    setRedirecting(true);
    try {
      await login(returnTo);
    } finally {
      setRedirecting(false);
    }
  }

  return (
    <div
      style={{
        position: 'relative',
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <SHBAmbientBackground />

      <motion.div
        style={{ position: 'relative', zIndex: 1, width: '100%', maxWidth: 400 }}
        initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        <Card style={{ textAlign: 'center', borderRadius: 16 }} styles={{ body: { padding: 32 } }}>
          <AnimatedSHBLogo size="large" glow glowIntensity="subtle" />

          <Typography.Title level={3} style={{ marginTop: 16, marginBottom: 4 }}>
            SHB AI Assistant
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 24 }}>
            Trợ lý tín dụng thông minh dành cho cán bộ ngân hàng. Đăng nhập bằng tài
            khoản nội bộ để tiếp tục.
          </Typography.Paragraph>

          <Button
            type="primary"
            size="large"
            block
            icon={<LoginOutlined />}
            loading={redirecting}
            onClick={() => void handleLogin()}
          >
            Đăng nhập
          </Button>
        </Card>
      </motion.div>
    </div>
  );
}
