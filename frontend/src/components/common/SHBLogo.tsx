import { useState } from 'react';
import styles from './SHBLogo.module.css';

export interface SHBLogoProps {
  variant?: 'default' | 'white';
  size?: 'small' | 'medium' | 'large';
  /** Hiển thị tên sản phẩm "SH-AI" bên cạnh logo. */
  showProductName?: boolean;
  className?: string;
}

const SIZE_CLASS: Record<NonNullable<SHBLogoProps['size']>, string> = {
  small: styles.sizeSmall,
  medium: styles.sizeMedium,
  large: styles.sizeLarge,
};

/**
 * Logo SHB chính thức.
 *
 * Asset được lưu local trong `public/brand/` (xem README ở đó để biết nguồn).
 * Không hotlink từ CDN, không dùng CSS filter để tạo biến thể trắng —
 * biến thể trắng là file riêng do SHB cung cấp.
 */
export function SHBLogo({
  variant = 'default',
  size = 'medium',
  showProductName = false,
  className,
}: SHBLogoProps) {
  const [assetFailed, setAssetFailed] = useState(false);
  const isWhite = variant === 'white';

  const source = isWhite ? '/brand/shb-logo-white.svg' : '/brand/shb-logo.svg';

  const rootClassName = [styles.logo, SIZE_CLASS[size], className].filter(Boolean).join(' ');

  return (
    <span className={rootClassName}>
      {assetFailed ? (
        // Fallback an toàn nếu asset không tải được — không dựng lại logo bằng CSS.
        <span className={styles.fallback}>SHB</span>
      ) : (
        <img
          src={source}
          alt="SHB"
          className={styles.image}
          onError={() => setAssetFailed(true)}
          draggable={false}
        />
      )}

      {showProductName && (
        <>
          <span
            className={[styles.separator, isWhite ? styles.separatorWhite : '']
              .filter(Boolean)
              .join(' ')}
            aria-hidden="true"
          />
          <span className={styles.productName}>
            <span
              className={[styles.productTitle, isWhite ? styles.productTitleWhite : '']
                .filter(Boolean)
                .join(' ')}
            >
              SH-AI
            </span>
            <span
              className={[styles.productTagline, isWhite ? styles.productTaglineWhite : '']
                .filter(Boolean)
                .join(' ')}
            >
              Hệ chuyên gia số nội bộ
            </span>
          </span>
        </>
      )}
    </span>
  );
}
