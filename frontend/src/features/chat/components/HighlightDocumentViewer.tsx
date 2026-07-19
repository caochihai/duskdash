import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Tooltip, Typography } from 'antd';
import {
  ArrowLeftOutlined,
  CloseOutlined,
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import type { DocumentRegion } from '@/features/chat/constants/demoDocuments';
import styles from './HighlightDocumentViewer.module.css';

export interface HighlightDocument {
  name: string;
  url: string;
  /**
   * Các vùng được agent trích dẫn, toạ độ chuẩn hoá 0..1 lấy từ OCR.
   * Rỗng nghĩa là hồ sơ chưa có dẫn chứng nào trỏ tới — vẫn xem được ảnh gốc.
   */
  regions?: DocumentRegion[];
  /** Vùng cần khoanh đỏ và cuộn tới ngay khi mở. */
  activeRegionId?: string;
}

interface HighlightDocumentViewerProps {
  document: HighlightDocument;
  /** Quay lại phần thông tin khách hàng trong panel. */
  onBack: () => void;
  /** Đóng hẳn panel bên phải. */
  onClose: () => void;
}

const ZOOM_STEPS = [1, 1.5, 2, 3];

/**
 * Viewer hồ sơ trong panel phải: ảnh scan gốc + khung đánh dấu vẽ đè lên đúng
 * toạ độ mà OCR trả về.
 *
 * Vùng đang được trỏ tới khoanh ĐỎ; các vùng còn lại khoanh cam để chuyên viên
 * thấy toàn bộ dẫn chứng trên cùng một trang. Bấm khung (hoặc dùng nút ‹ ›) để
 * chuyển giữa các dẫn chứng — đây là đường đi từ câu trả lời về đúng chỗ trên
 * giấy tờ.
 */
export function HighlightDocumentViewer({
  document,
  onBack,
  onClose,
}: HighlightDocumentViewerProps) {
  const regions = document.regions ?? [];
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);

  const [activeId, setActiveId] = useState<string | undefined>(
    document.activeRegionId ?? regions[0]?.id,
  );
  const [zoom, setZoom] = useState(1);

  // Câu trả lời trỏ sang vùng khác -> nhảy theo.
  useEffect(() => {
    setActiveId(document.activeRegionId ?? regions[0]?.id);
  }, [document.activeRegionId, document.url, regions]);

  // Đưa vùng đang trỏ vào tầm nhìn, kể cả khi đang phóng to.
  useEffect(() => {
    if (!activeId) return;
    const timer = window.setTimeout(() => {
      activeRef.current?.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [activeId, zoom]);

  const activeIndex = regions.findIndex((region) => region.id === activeId);
  const activeRegion = activeIndex >= 0 ? regions[activeIndex] : undefined;

  const step = useCallback(
    (delta: number) => {
      if (regions.length === 0) return;
      const next = (activeIndex + delta + regions.length) % regions.length;
      setActiveId(regions[next].id);
    },
    [activeIndex, regions],
  );

  const changeZoom = useCallback((delta: number) => {
    setZoom((current) => {
      const index = ZOOM_STEPS.indexOf(current);
      const nextIndex = Math.min(ZOOM_STEPS.length - 1, Math.max(0, index + delta));
      return ZOOM_STEPS[nextIndex];
    });
  }, []);

  return (
    <div className={styles.viewer}>
      <div className={styles.header}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={onBack}
          aria-label="Quay lại thông tin khách hàng"
        />
        <div className={styles.headerText}>
          <Typography.Text strong style={{ color: '#2F2E79', display: 'block' }} ellipsis>
            {document.name}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {regions.length > 0
              ? `${regions.length} vị trí được trích dẫn — khung đỏ là dẫn chứng đang xem`
              : 'Hồ sơ gốc do khách hàng cung cấp'}
          </Typography.Text>
        </div>
        <Button type="text" icon={<CloseOutlined />} onClick={onClose} aria-label="Đóng panel" />
      </div>

      {regions.length > 0 && (
        <div className={styles.toolbar}>
          <Button
            size="small"
            icon={<LeftOutlined />}
            onClick={() => step(-1)}
            disabled={regions.length < 2}
            aria-label="Dẫn chứng trước"
          />
          <Typography.Text style={{ fontSize: 12, minWidth: 92, textAlign: 'center' }}>
            Dẫn chứng {activeIndex >= 0 ? activeIndex + 1 : 1}/{regions.length}
          </Typography.Text>
          <Button
            size="small"
            icon={<RightOutlined />}
            onClick={() => step(1)}
            disabled={regions.length < 2}
            aria-label="Dẫn chứng sau"
          />

          <span style={{ flex: 1 }} />

          <Tooltip title="Thu nhỏ">
            <Button
              size="small"
              icon={<ZoomOutOutlined />}
              onClick={() => changeZoom(-1)}
              disabled={zoom === ZOOM_STEPS[0]}
              aria-label="Thu nhỏ"
            />
          </Tooltip>
          <Typography.Text type="secondary" style={{ fontSize: 12, minWidth: 38, textAlign: 'center' }}>
            {Math.round(zoom * 100)}%
          </Typography.Text>
          <Tooltip title="Phóng to">
            <Button
              size="small"
              icon={<ZoomInOutlined />}
              onClick={() => changeZoom(1)}
              disabled={zoom === ZOOM_STEPS[ZOOM_STEPS.length - 1]}
              aria-label="Phóng to"
            />
          </Tooltip>
        </div>
      )}

      <div className={styles.scroll} ref={scrollRef}>
        <div className={styles.stage} style={{ width: `${zoom * 100}%` }}>
          <img className={styles.page} src={document.url} alt={document.name} />

          {regions.map((region, index) => {
            const isActive = region.id === activeId;
            return (
              <button
                key={region.id}
                type="button"
                ref={isActive ? activeRef : undefined}
                className={[styles.region, isActive ? styles.regionActive : '']
                  .filter(Boolean)
                  .join(' ')}
                style={{
                  left: `${(region.x - 0.004) * 100}%`,
                  top: `${(region.y - 0.004) * 100}%`,
                  width: `${(region.w + 0.008) * 100}%`,
                  height: `${(region.h + 0.008) * 100}%`,
                }}
                onClick={() => setActiveId(region.id)}
                aria-label={`Dẫn chứng ${index + 1}: ${region.quote}`}
                aria-current={isActive}
                title={region.label ?? region.quote}
              >
                <span
                  className={[styles.regionBadge, isActive ? styles.regionBadgeActive : '']
                    .filter(Boolean)
                    .join(' ')}
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {activeRegion && (
        <div className={styles.quoteBar}>
          <span className={styles.quoteLabel}>
            {activeRegion.label ?? 'Nội dung tại vùng được đánh dấu'}
          </span>
          <span className={styles.quoteText}>“{activeRegion.quote}”</span>
        </div>
      )}
    </div>
  );
}
