import { Button, Image, Typography } from 'antd';
import { ArrowLeftOutlined, CloseOutlined } from '@ant-design/icons';

export interface HighlightDocument {
  name: string;
  url: string;
}

interface HighlightDocumentViewerProps {
  document: HighlightDocument;
  /** Quay lại phần thông tin khách hàng trong panel. */
  onBack: () => void;
  /** Đóng hẳn panel bên phải. */
  onClose: () => void;
}

/**
 * Viewer chiếm panel phải khi cán bộ bấm vào một ảnh hồ sơ đã highlight:
 * hiển thị đúng ảnh gốc đã upload với khung màu 🔴🟠🟡 vẽ trực tiếp,
 * bấm vào ảnh để phóng to toàn màn hình.
 */
export function HighlightDocumentViewer({ document, onBack, onClose }: HighlightDocumentViewerProps) {
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#FFFDF9',
        borderLeft: '1px solid #EAE3DA',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '12px 16px',
          borderBottom: '1px solid #EAE3DA',
          background: '#FFFFFF',
        }}
      >
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={onBack}
          aria-label="Quay lại thông tin khách hàng"
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <Typography.Text strong style={{ color: '#2F2E79', display: 'block' }} ellipsis>
            {document.name}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Khung màu do SH-AI đánh dấu trực tiếp trên hồ sơ gốc — bấm ảnh để phóng to
          </Typography.Text>
        </div>
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} aria-label="Đóng panel" />
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        <Image
          src={document.url}
          alt={document.name}
          style={{ width: '100%', borderRadius: 12, border: '1px solid #EAE3DA' }}
        />
      </div>
    </div>
  );
}
