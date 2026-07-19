import rawDocuments from './demoDocumentLines.json';
import { normalizeVietnamese } from '@/utils/detectSensitiveContent';

/**
 * Hồ sơ demo — ảnh scan THẬT của bộ hồ sơ CR-A01 (Công ty CP Bao bì VinaNova)
 * kèm toạ độ dòng chữ do **Azure Document Intelligence `prebuilt-read`** trả về.
 *
 * Toạ độ đã chuẩn hoá 0..1 theo khổ trang, nên khung đánh dấu vẽ bằng phần trăm
 * sẽ khớp tuyệt đối ở mọi kích thước hiển thị — không phụ thuộc zoom hay DPI.
 *
 * Đây là bản thu nhỏ của `document.document_line` (migration V019): backend thật
 * lưu đúng những trường này, và `Citation.bbox` trỏ về chúng.
 */

export interface DocumentLine {
  text: string;
  /** Toạ độ chuẩn hoá 0..1: góc trái-trên + rộng/cao. */
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DemoDocument {
  id: string;
  slug: string;
  title: string;
  kind: 'profile' | 'financial' | 'legal';
  url: string;
  width: number;
  height: number;
  lines: DocumentLine[];
}

export const DEMO_DOCUMENTS = rawDocuments as DemoDocument[];

/** Khách hàng demo có hồ sơ scan thật kèm toạ độ. */
export const DOCUMENT_CUSTOMER_ID = 'cus-003';

export function findDocumentById(documentId: string): DemoDocument | undefined {
  return DEMO_DOCUMENTS.find((doc) => doc.id === documentId);
}

export function findDocumentByKind(kind: DemoDocument['kind']): DemoDocument | undefined {
  return DEMO_DOCUMENTS.find((doc) => doc.kind === kind);
}

/** Một vùng được đánh dấu trên hồ sơ — chính là nơi agent lấy dẫn chứng. */
export interface DocumentRegion {
  id: string;
  documentId: string;
  page: number;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Nguyên văn dòng chữ tại vùng này. */
  quote: string;
  /** Nhãn ngắn giải thích vì sao vùng này được trích. */
  label?: string;
}

/**
 * Tìm dòng chữ khớp nhất với một mẩu nội dung, trả về vùng toạ độ của nó.
 *
 * Khớp theo tiếng Việt đã bỏ dấu để câu trích trong câu trả lời không cần trùng
 * khít từng ký tự với kết quả OCR. Trả `null` khi không tìm thấy — quan trọng:
 * KHÔNG bịa ra toạ độ, vì một trích dẫn không resolve được phải bị loại bỏ
 * (bất biến chống bịa nguồn của `compose.verify_claim`).
 */
export function locateInDocument(
  documentId: string,
  needle: string,
  label?: string,
): DocumentRegion | null {
  const doc = findDocumentById(documentId);
  if (!doc) return null;

  const target = normalizeVietnamese(needle).trim();
  if (!target) return null;

  let best: { line: DocumentLine; index: number; score: number } | null = null;

  doc.lines.forEach((line, index) => {
    const candidate = normalizeVietnamese(line.text);
    let score = 0;

    /*
     * Ngưỡng phải CHẶT. Khớp lỏng sẽ khoanh đỏ nhầm chỗ, mà một dẫn chứng trỏ
     * sai vị trí còn tai hại hơn là không có dẫn chứng: chuyên viên tin vào
     * khung đỏ đó để ra quyết định tín dụng.
     */
    if (candidate === target) {
      score = 1000;
    } else if (target.length >= 6 && candidate.includes(target)) {
      score = 500 + target.length;
    } else if (candidate.length >= 10 && target.includes(candidate)) {
      score = 300 + candidate.length;
    } else {
      // Trùng từ: cần ít nhất 2 từ VÀ phủ được phần lớn câu cần dò.
      const words = target.split(/\s+/).filter((word) => word.length > 2);
      const hit = words.filter((word) => candidate.includes(word)).length;
      if (hit >= 2 && hit / words.length >= 0.6) score = hit * 10;
    }

    if (score > 0 && (!best || score > best.score)) best = { line, index, score };
  });

  if (!best) return null;

  const { line, index } = best as { line: DocumentLine; index: number; score: number };
  return {
    id: `${doc.id}-l${index}`,
    documentId: doc.id,
    page: 1,
    x: line.x,
    y: line.y,
    w: line.w,
    h: line.h,
    quote: line.text,
    ...(label ? { label } : {}),
  };
}

/** Gộp nhiều vùng liền kề thành một khung bao — dùng khi dẫn chứng trải vài dòng. */
export function mergeRegions(regions: DocumentRegion[], id: string, label?: string): DocumentRegion | null {
  if (regions.length === 0) return null;
  if (regions.length === 1) return regions[0];

  const x = Math.min(...regions.map((r) => r.x));
  const y = Math.min(...regions.map((r) => r.y));
  const right = Math.max(...regions.map((r) => r.x + r.w));
  const bottom = Math.max(...regions.map((r) => r.y + r.h));

  return {
    id,
    documentId: regions[0].documentId,
    page: regions[0].page,
    x,
    y,
    w: right - x,
    h: bottom - y,
    quote: regions.map((r) => r.quote).join(' '),
    ...(label ? { label } : {}),
  };
}
