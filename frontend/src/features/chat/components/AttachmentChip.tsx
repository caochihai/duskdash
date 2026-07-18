import { Button, Progress, Tooltip } from 'antd';
import {
  CloseOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ComponentType } from 'react';
import { createElement } from 'react';
import { formatFileSize, getFileExtensionLabel } from '@/utils/formatFileSize';
import { shbColors } from '@/theme/tokens';
import type { ChatAttachment } from '@/types/attachment';
import styles from './AttachmentChip.module.css';

export interface AttachmentChipProps {
  attachment: ChatAttachment;
  readOnly?: boolean;
  onRemove?: (id: string) => void;
  onRetry?: (id: string) => void;
}

/** Chọn icon theo MIME type — icon lấy từ @ant-design/icons. */
function resolveIcon(mimeType: string): ComponentType {
  if (mimeType === 'application/pdf') return FilePdfOutlined;
  if (mimeType.startsWith('image/')) return FileImageOutlined;
  if (mimeType.includes('word')) return FileWordOutlined;
  if (mimeType.includes('sheet') || mimeType.includes('excel')) return FileExcelOutlined;
  return FileOutlined;
}

/** Thẻ hiển thị một tài liệu đính kèm. */
export function AttachmentChip({ attachment, readOnly = false, onRemove, onRetry }: AttachmentChipProps) {
  const isError = attachment.status === 'error';
  const isUploading = attachment.status === 'uploading';
  const Icon = isError ? WarningOutlined : resolveIcon(attachment.mimeType);

  return (
    <div className={[styles.chip, isError ? styles.chipError : ''].filter(Boolean).join(' ')}>
      <span className={[styles.icon, isError ? styles.iconError : ''].filter(Boolean).join(' ')} aria-hidden="true">
        {createElement(Icon)}
      </span>

      <span className={styles.body}>
        <Tooltip title={attachment.name}>
          <span className={styles.name}>{attachment.name}</span>
        </Tooltip>

        <span className={[styles.meta, isError ? styles.metaError : ''].filter(Boolean).join(' ')}>
          {isError
            ? (attachment.errorMessage ?? 'Tải lên thất bại')
            : isUploading
              ? `Đang tải lên ${attachment.progress ?? 0}%`
              : `${getFileExtensionLabel(attachment.name)} • ${formatFileSize(attachment.size)}`}
        </span>

        {isUploading && (
          <span className={styles.progressWrap}>
            <Progress
              percent={attachment.progress ?? 0}
              size="small"
              showInfo={false}
              strokeColor={shbColors.orange[500]}
            />
          </span>
        )}
      </span>

      {!readOnly && isError && onRetry && (
        <Button
          className={styles.remove}
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => onRetry(attachment.id)}
          aria-label={`Thử tải lại ${attachment.name}`}
        />
      )}

      {!readOnly && onRemove && (
        <Button
          className={styles.remove}
          type="text"
          size="small"
          icon={<CloseOutlined />}
          onClick={() => onRemove(attachment.id)}
          aria-label={`Xoá tài liệu ${attachment.name}`}
        />
      )}
    </div>
  );
}
