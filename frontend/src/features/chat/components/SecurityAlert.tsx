import { Alert } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { AnimatePresence, motion } from 'motion/react';
import type { SensitiveDetection } from '@/utils/detectSensitiveContent';

export interface SecurityAlertProps {
  detection: SensitiveDetection | null;
  onClose?: () => void;
}

/** Cảnh báo bảo mật hiển thị khi phát hiện nội dung nhạy cảm trong composer. */
export function SecurityAlert({ detection, onClose }: SecurityAlertProps) {
  return (
    <AnimatePresence initial={false}>
      {detection && (
        <motion.div
          initial={{ opacity: 0, height: 0, marginBottom: 0 }}
          animate={{ opacity: 1, height: 'auto', marginBottom: 10 }}
          exit={{ opacity: 0, height: 0, marginBottom: 0 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          style={{ overflow: 'hidden' }}
        >
          <Alert
            // Thông tin xác thực là rủi ro cao -> mức warning; còn lại là info.
            type={detection.kind === 'credential' ? 'warning' : 'info'}
            showIcon
            icon={<SafetyCertificateOutlined />}
            message={detection.message}
            closable={Boolean(onClose)}
            onClose={onClose}
            role="alert"
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
