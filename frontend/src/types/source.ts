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

/**
 * Địa chỉ chính xác của dẫn chứng trên hồ sơ gốc.
 *
 * Tương ứng `Citation.bbox` ở backend (`libs/contracts/citation.py`), resolve
 * qua `GET /citations/{id}/resolve` về bảng `document.document_line`. Có trường
 * này thì giao diện mở được đúng trang, đúng vùng và khoanh đỏ.
 */
export interface SourceLocator {
  documentId: string;
  documentTitle: string;
  documentUrl: string;
  page: number;
  /** Vùng cần khoanh đỏ khi mở hồ sơ. */
  regionId: string;
}

export interface ChatSource {
  id: string;
  title: string;
  type: SourceType;
  url?: string;
  excerpt: string;
  updatedAt?: string;
  documentName?: string;
  /** Có mặt khi nguồn trỏ về một vị trí cụ thể trên hồ sơ đã OCR. */
  locator?: SourceLocator;
}
