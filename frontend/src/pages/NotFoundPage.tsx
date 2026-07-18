import { Button, Result } from 'antd';
import { HomeOutlined } from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { AnimatedSHBLogo } from '@/components/common/AnimatedSHBLogo';
import { SHBAmbientBackground } from '@/components/ai/SHBAmbientBackground';

/** Trang 404 — giữ đúng nhận diện SHB. */
export default function NotFoundPage() {
  const navigate = useNavigate();
  const prefersReducedMotion = useReducedMotion();

  return (
    <div
      style={{
        position: 'relative',
        minHeight: '100dvh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <SHBAmbientBackground />

      <motion.div
        style={{ position: 'relative', zIndex: 1, textAlign: 'center' }}
        initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        <AnimatedSHBLogo size="large" glow glowIntensity="subtle" />

        <Result
          status="404"
          title="404"
          subTitle="Rất tiếc, trang bạn tìm không tồn tại hoặc đã được chuyển đi."
          extra={
            <Button type="primary" icon={<HomeOutlined />} onClick={() => navigate('/')}>
              Trở về trang trò chuyện
            </Button>
          }
        />
      </motion.div>
    </div>
  );
}
