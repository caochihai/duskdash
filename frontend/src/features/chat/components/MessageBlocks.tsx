import { Alert, Button } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import { MarkdownContent } from './MarkdownContent';
import { LoanEstimateCard } from '@/features/customer/components/LoanEstimateCard';
import { ProductRecommendationCard } from './ProductRecommendationCard';
import { LazyLoanBreakdownChart } from '@/components/charts/LazyLoanBreakdownChart';
import { DataTable } from '@/components/tables/DataTable';
import { LoanApprovalCard } from '@/features/customer/components/LoanApprovalCard';
import { CustomerSummaryCard } from '@/features/customer/components/CustomerSummaryCard';
import type { MessageBlock } from '@/types/chat';
import type { LoanApplication, LoanApplicationStatus } from '@/types/customer';
import styles from './AssistantMessage.module.css';

export interface MessageBlocksProps {
  blocks: MessageBlock[];
  /** Gửi một prompt mới (CTA, điều chỉnh thông số...). */
  onPrompt: (prompt: string) => void;
  disabled?: boolean;
  /** Mở hồ sơ khách hàng (từ loanApproval / customerSummary block). */
  onViewCustomer?: (customerId: string) => void;
  /** Ghi nhận quyết định phê duyệt. */
  onLoanDecision?: (
    application: LoanApplication,
    status: LoanApplicationStatus,
    note: string,
  ) => void;
}

interface TableRow {
  key: string;
  [column: string]: string;
}

/**
 * Render nội dung phong phú của câu trả lời AI từ union `MessageBlock`.
 *
 * Mỗi loại block map tới một component chuyên biệt — không có HTML thô,
 * không `dangerouslySetInnerHTML`.
 */
export function MessageBlocks({
  blocks,
  onPrompt,
  disabled = false,
  onViewCustomer,
  onLoanDecision,
}: MessageBlocksProps) {
  return (
    <div className={styles.blocks}>
      {blocks.map((block, index) => {
        const key = `${block.type}-${index}`;

        switch (block.type) {
          case 'markdown':
            return <MarkdownContent key={key} content={block.content} />;

          case 'loanEstimate':
            return (
              <LoanEstimateCard
                key={key}
                estimate={block}
                onAdjust={
                  disabled
                    ? undefined
                    : () =>
                        onPrompt('Tôi muốn điều chỉnh số tiền vay và thời hạn để xem lại ước tính.')
                }
              />
            );

          case 'table': {
            const columns = block.columns.map((column) => ({
              title: column.title,
              dataIndex: column.key,
              key: column.key,
              align: column.align ?? 'left',
            }));

            // Row key ổn định từ dữ liệu, không dùng index.
            const rows: TableRow[] = block.rows.map((row, rowIndex) => ({
              ...row,
              key: `${key}-row-${rowIndex}`,
            }));

            return (
              <div key={key} className={styles.tableBlock}>
                {block.title && <h3 className={styles.blockTitle}>{block.title}</h3>}
                <DataTable<TableRow>
                  columns={columns}
                  dataSource={rows}
                  rowKey="key"
                  size="small"
                  pagination={false}
                />
                {block.footnote && <span className={styles.footnote}>{block.footnote}</span>}
              </div>
            );
          }

          case 'chart':
            return (
              <div key={key} className={styles.chartBlock}>
                {block.title && <h3 className={styles.blockTitle}>{block.title}</h3>}
                {block.description && <p className={styles.blockDescription}>{block.description}</p>}
                <LazyLoanBreakdownChart
                  data={block.data}
                  chartType={block.chartType}
                  valueFormat={block.valueFormat}
                  description={
                    block.description
                      ? `${block.description} ${block.data
                          .map((item) => `${item.category}: ${item.value.toLocaleString('vi-VN')}`)
                          .join('; ')}.`
                      : undefined
                  }
                />
              </div>
            );

          case 'product':
            return (
              <ProductRecommendationCard
                key={key}
                title={block.title}
                description={block.description}
                benefits={block.benefits}
                badge={block.badge}
                primaryActionLabel={block.primaryActionLabel}
                secondaryActionLabel={block.secondaryActionLabel}
                onPrimaryAction={() => onPrompt(`Cho tôi biết thêm về ${block.title}.`)}
                onSecondaryAction={
                  block.secondaryActionLabel
                    ? () => onPrompt(`${block.secondaryActionLabel} cho ${block.title}.`)
                    : undefined
                }
              />
            );

          case 'alert':
            return (
              <Alert
                key={key}
                type={block.variant}
                showIcon
                message={block.title}
                description={block.content}
              />
            );

          case 'cta':
            return (
              <div key={key} className={styles.ctaRow}>
                {block.actions.map((action) => (
                  <Button
                    key={action.id}
                    type={action.primary ? 'primary' : 'default'}
                    disabled={disabled}
                    onClick={() => action.prompt && onPrompt(action.prompt)}
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            );

          case 'disclaimer':
            return (
              <p key={key} className={styles.disclaimer}>
                <InfoCircleOutlined className={styles.disclaimerIcon} aria-hidden="true" />
                <span>{block.content}</span>
              </p>
            );

          case 'loanApproval':
            return (
              <LoanApprovalCard
                key={key}
                application={block.application}
                onViewCustomer={onViewCustomer}
                onDecision={(status, note) => onLoanDecision?.(block.application, status, note)}
              />
            );

          case 'customerSummary':
            return (
              <CustomerSummaryCard
                key={key}
                customer={block.customer}
                onViewDetail={onViewCustomer}
              />
            );

          default:
            return null;
        }
      })}
    </div>
  );
}
