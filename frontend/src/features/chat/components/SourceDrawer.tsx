import { Button, Drawer, Grid, Skeleton, Tag } from 'antd';
import { ExportOutlined, FileTextOutlined } from '@ant-design/icons';
import { motion, useReducedMotion } from 'motion/react';
import { EmptyState } from '@/components/common/EmptyState';
import { formatDate } from '@/utils/formatDate';
import { SOURCE_TYPE_LABEL, type ChatSource, type SourceType } from '@/types/source';
import styles from './SourceDrawer.module.css';

export interface SourceDrawerProps {
  open: boolean;
  onClose: () => void;
  sources: ChatSource[];
  loading?: boolean;
}

/** Màu Tag theo loại nguồn — kèm nhãn chữ, không chỉ dựa vào màu. */
const SOURCE_TAG_COLOR: Record<SourceType, string> = {
  policy: 'blue',
  product: 'orange',
  fee: 'gold',
  faq: 'green',
  attachment: 'purple',
  procedure: 'cyan',
  announcement: 'magenta',
};

/**
 * Drawer hiển thị nguồn tham khảo của câu trả lời.
 *
 * Ant Design Drawer đã quản lý focus trap và trả focus về phần tử trigger
 * (nút "Xem nguồn") khi đóng.
 */
export function SourceDrawer({ open, onClose, sources, loading = false }: SourceDrawerProps) {
  const screens = Grid.useBreakpoint();
  const prefersReducedMotion = useReducedMotion();

  // Mobile: drawer gần full screen để đọc trích dẫn dễ hơn.
  const isMobile = !screens.md;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      width={isMobile ? '100%' : 420}
      destroyOnHidden
      title={
        <span className={styles.header}>
          <span className={styles.title}>Nguồn tham khảo</span>
          <span className={styles.count}>
            {loading ? 'Đang tải nguồn…' : `${sources.length} nguồn được trích dẫn`}
          </span>
        </span>
      }
    >
      {loading ? (
        <div className={styles.list}>
          {[0, 1, 2].map((index) => (
            <div key={index} className={styles.card}>
              <Skeleton active paragraph={{ rows: 2 }} title={{ width: '60%' }} />
            </div>
          ))}
        </div>
      ) : sources.length === 0 ? (
        <div className={styles.emptyWrap}>
          <EmptyState
            title="Chưa có nguồn tham khảo"
            description="Câu trả lời này không trích dẫn tài liệu nào."
          />
        </div>
      ) : (
        <>
          <div className={styles.list}>
            {sources.map((source, index) => (
              <motion.article
                key={source.id}
                className={styles.card}
                initial={prefersReducedMotion ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                // Stagger nhẹ khi drawer mở.
                transition={{ duration: 0.24, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
              >
                <div className={styles.cardHeader}>
                  <h3 className={styles.cardTitle}>{source.title}</h3>
                  <Tag color={SOURCE_TAG_COLOR[source.type]}>{SOURCE_TYPE_LABEL[source.type]}</Tag>
                </div>

                <blockquote className={styles.excerpt}>{source.excerpt}</blockquote>

                <div className={styles.footer}>
                  {source.documentName ? (
                    <span className={styles.docName}>
                      <FileTextOutlined aria-hidden="true" />
                      {source.documentName}
                    </span>
                  ) : (
                    <span className={styles.updated}>
                      {source.updatedAt ? `Cập nhật ${formatDate(source.updatedAt)}` : 'Tài liệu nội bộ'}
                    </span>
                  )}

                  {source.url && (
                    <Button
                      type="link"
                      size="small"
                      icon={<ExportOutlined />}
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Mở nguồn
                    </Button>
                  )}
                </div>
              </motion.article>
            ))}
          </div>

          <p className={styles.note}>
            Nguồn tham khảo trong phiên bản demo là dữ liệu minh hoạ. Khi kết nối hệ thống thật,
            phần này sẽ hiển thị tài liệu chính thức của SHB.
          </p>
        </>
      )}
    </Drawer>
  );
}
