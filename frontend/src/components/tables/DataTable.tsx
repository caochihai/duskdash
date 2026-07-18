import { Table } from 'antd';
import type { TableProps } from 'antd';
import { EmptyState } from '@/components/common/EmptyState';

export interface DataTableProps<TRecord> {
  columns: TableProps<TRecord>['columns'];
  dataSource: TRecord[];
  /** Bắt buộc: khoá dòng ổn định, không dùng index. */
  rowKey: keyof TRecord | ((record: TRecord) => string);
  loading?: boolean;
  pagination?: TableProps<TRecord>['pagination'];
  size?: TableProps<TRecord>['size'];
  emptyTitle?: string;
  emptyDescription?: string;
  /** Bảng hẹp hơn giá trị này sẽ scroll ngang thay vì vỡ layout. */
  scrollX?: number | string;
  className?: string;
  bordered?: boolean;
}

/**
 * Adapter Table generic dựng trên Ant Design Table.
 * Không chứa logic nghiệp vụ SHB, không hard-code dữ liệu.
 */
export function DataTable<TRecord extends object>({
  columns,
  dataSource,
  rowKey,
  loading = false,
  pagination = false,
  size = 'middle',
  emptyTitle = 'Chưa có dữ liệu',
  emptyDescription,
  scrollX = 'max-content',
  className,
  bordered = false,
}: DataTableProps<TRecord>) {
  const resolveRowKey =
    typeof rowKey === 'function'
      ? rowKey
      : (record: TRecord) => String(record[rowKey as keyof TRecord]);

  return (
    <Table<TRecord>
      className={className}
      columns={columns}
      dataSource={dataSource}
      rowKey={resolveRowKey}
      loading={loading}
      pagination={pagination}
      size={size}
      bordered={bordered}
      // Cuộn ngang trong phạm vi bảng — không đẩy tràn cả trang.
      scroll={{ x: scrollX }}
      locale={{
        emptyText: <EmptyState compact title={emptyTitle} description={emptyDescription} />,
      }}
    />
  );
}
