import { Typography } from 'antd';
import { SECURITY_MESSAGES } from '@/features/chat/constants/securityKeywords';

const { Text } = Typography;

export interface AIDisclaimerProps {
  /** Mặc định dùng disclaimer chuẩn dưới composer. */
  content?: string;
  align?: 'center' | 'left';
}

/** Dòng cảnh báo nhỏ dưới composer. Font nhỏ nhưng vẫn đọc được (12px). */
export function AIDisclaimer({
  content = SECURITY_MESSAGES.composerDisclaimer,
  align = 'center',
}: AIDisclaimerProps) {
  return (
    <Text
      type="secondary"
      style={{
        display: 'block',
        fontSize: 12,
        lineHeight: 1.5,
        textAlign: align,
        maxWidth: 680,
        margin: align === 'center' ? '0 auto' : undefined,
      }}
    >
      {content}
    </Text>
  );
}
