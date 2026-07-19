/**
 * Vùng dẫn chứng trên hồ sơ — sinh từ DỮ LIỆU THẬT:
 * `metadata.highlight_segments` của backend (vision gemma-4-31B đọc ảnh
 * người dùng upload), KHÔNG phải mock. Toạ độ chuẩn hoá 0..1 theo khổ ảnh.
 */
export interface DocumentRegion {
  id: string;
  /** Toạ độ chuẩn hoá 0..1: góc trái-trên + rộng/cao. */
  x: number;
  y: number;
  w: number;
  h: number;
  /** Nguyên văn đoạn chữ được trích tại vùng này. */
  quote: string;
  /** Nhãn ngắn: mức độ + lý do (+ căn cứ pháp lý nếu có). */
  label?: string;
}
