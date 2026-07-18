/** Loại nguồn tham khảo mà SH-AI trích dẫn. */
export type SourceType =
  | 'policy'
  | 'product'
  | 'fee'
  | 'faq'
  | 'attachment'
  | 'procedure'
  | 'announcement';

/** Nhãn tiếng Việt hiển thị cho từng loại nguồn. */
export const SOURCE_TYPE_LABEL: Record<SourceType, string> = {
  policy: 'Chính sách SHB',
  product: 'Trang sản phẩm',
  fee: 'Biểu phí',
  faq: 'FAQ',
  attachment: 'Tài liệu tải lên',
  procedure: 'Quy trình nghiệp vụ',
  announcement: 'Thông báo',
};

export interface ChatSource {
  id: string;
  title: string;
  type: SourceType;
  url?: string;
  excerpt: string;
  updatedAt?: string;
  documentName?: string;
}
