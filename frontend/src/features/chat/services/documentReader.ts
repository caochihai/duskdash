import { DEMO_DOCUMENTS, type DemoDocument, type DocumentLine, type DocumentRegion } from '../constants/demoDocuments';

/**
 * BƯỚC 1 CỦA PIPELINE: đọc dữ kiện từ văn bản OCR.
 *
 *   OCR (Azure prebuilt-read) → [documentReader] → dữ kiện có toạ độ → LLM → báo cáo
 *
 * Chỗ này KHÔNG viết sẵn nội dung báo cáo. Nó chỉ bóc các cặp "nhãn: giá trị" và
 * các dòng bảng từ chính chữ mà OCR đọc được, kèm theo toạ độ của Ô CHỨA GIÁ TRỊ.
 * Nhờ vậy khi chuyên viên bấm vào một số trong báo cáo, khung đỏ rơi đúng vào con
 * số đó trên ảnh scan chứ không phải vào cái nhãn bên cạnh.
 *
 * Hệ quả quan trọng: dữ kiện nào không có trong tài liệu thì không bóc ra được,
 * nên báo cáo không thể khẳng định điều mà giấy tờ không nói.
 */

/**
 * Dung sai theo trục dọc để coi hai dòng là "cùng một hàng" (tỉ lệ trang).
 *
 * Các hàng trong hồ sơ này cách nhau khoảng 0,013. Dung sai phải NHỎ HƠN HẲN
 * khoảng đó, nếu không nhãn sẽ với sang giá trị của hàng ngay bên dưới —
 * "Vốn điều lệ" ăn nhầm dòng tình trạng pháp lý là kiểu lỗi đã gặp.
 */
const ROW_TOLERANCE = 0.008;

/** Khoảng cách ngang tối thiểu giữa nhãn và giá trị. */
const MIN_COLUMN_GAP = 0.04;

export interface ExtractedFact {
  /** Định danh ổn định để citation trỏ tới. */
  id: string;
  /** Nhãn đọc được, đã bỏ dấu ':' và gạch đầu dòng. */
  label: string;
  /** Giá trị nguyên văn OCR đọc được. */
  value: string;
  documentId: string;
  documentTitle: string;
  documentUrl: string;
  /** Vùng của Ô GIÁ TRỊ — dùng để khoanh đỏ. */
  region: DocumentRegion;
  /** Nguyên văn cả dòng, phục vụ hiển thị trong popover nguồn. */
  quote: string;
}

/**
 * Vùng chân trang (chữ ký, con dấu) bị bỏ qua: chữ ở đó rời rạc và hay ghép
 * nhầm thành cặp nhãn–giá trị vô nghĩa.
 */
const CONTENT_BOTTOM = 0.84;

function isLabelLine(line: DocumentLine): boolean {
  const text = line.text.trim();
  // Nhãn nằm ở cột trái và kết thúc bằng dấu hai chấm.
  return line.x < 0.32 && line.y < CONTENT_BOTTOM && text.endsWith(':');
}

function cleanLabel(raw: string): string {
  return raw
    .trim()
    .replace(/^[-–•]\s*/, '')
    .replace(/:$/, '')
    .trim();
}

function toRegion(doc: DemoDocument, line: DocumentLine, index: number, label: string): DocumentRegion {
  return {
    id: `${doc.id}-l${index}`,
    documentId: doc.id,
    page: 1,
    x: line.x,
    y: line.y,
    w: line.w,
    h: line.h,
    quote: line.text,
    label,
  };
}

/**
 * Bóc các cặp "Nhãn: Giá trị" nằm cùng một hàng.
 *
 * Giá trị là dòng gần nhất theo trục dọc, nằm bên phải nhãn và bản thân không
 * phải một nhãn khác. Không tìm được giá trị thì BỎ QUA cặp đó — thà thiếu dữ
 * kiện còn hơn ghép nhầm nhãn với số của hàng bên cạnh.
 */
export function extractLabeledFacts(doc: DemoDocument): ExtractedFact[] {
  const facts: ExtractedFact[] = [];

  doc.lines.forEach((line, index) => {
    if (!isLabelLine(line)) return;

    const label = cleanLabel(line.text);
    if (!label) return;

    let best: { line: DocumentLine; index: number; dy: number } | null = null;

    doc.lines.forEach((candidate, candidateIndex) => {
      if (candidateIndex === index) return;
      if (isLabelLine(candidate)) return;
      if (candidate.x < line.x + MIN_COLUMN_GAP) return;

      const dy = Math.abs(candidate.y - line.y);
      if (dy > ROW_TOLERANCE) return;

      /*
       * Ưu tiên Ô GẦN NHẤT BÊN PHẢI, không phải ô thẳng hàng nhất.
       *
       * Trang này có hai khối cạnh nhau: chỉ số tài chính ở cột x≈0,31 và bảng
       * tài sản bảo đảm ở cột x≈0,53. Nếu chấm theo độ lệch dọc, nhãn
       * "Tổng nợ vay/VCSH" sẽ ăn nhầm chữ "Quyền sử dụng đất và" của khối bên
       * phải vì nó tình cờ thẳng hàng hơn. Giá trị đúng luôn là ô sát nhãn nhất.
       */
      if (!best || candidate.x < best.line.x || (candidate.x === best.line.x && dy < best.dy)) {
        best = { line: candidate, index: candidateIndex, dy };
      }
    });

    if (!best) return;

    const picked = best as { line: DocumentLine; index: number; dy: number };
    facts.push({
      id: `fact-${doc.kind}-${picked.index}`,
      label,
      value: picked.line.text.trim(),
      documentId: doc.id,
      documentTitle: doc.title,
      documentUrl: doc.url,
      region: toRegion(doc, picked.line, picked.index, label),
      quote: `${label}: ${picked.line.text.trim()}`,
    });
  });

  return facts;
}

/**
 * Bóc một hàng của bảng tài chính: nhãn ở cột trái, các số theo cột năm.
 *
 * Trả về giá trị của CỘT ĐƯỢC CHỌN kèm toạ độ đúng ô số đó, để trích dẫn khoanh
 * trúng con số chứ không khoanh cả hàng.
 */
export function extractTableCell(
  doc: DemoDocument,
  rowLabel: string,
  columnX: number,
  tolerance = 0.06,
): ExtractedFact | null {
  const normalizedRow = rowLabel.toLowerCase();

  const rowIndex = doc.lines.findIndex(
    (line) => line.x < 0.32 && line.text.trim().toLowerCase().startsWith(normalizedRow),
  );
  if (rowIndex === -1) return null;

  const row = doc.lines[rowIndex];

  /*
   * Bảng có các hàng cách nhau chỉ ~0,013 nên dung sai dọc phải CHẶT HƠN nhiều
   * so với cặp nhãn–giá trị. Dùng dung sai rộng thì hàng "EBITDA" sẽ lấy nhầm
   * số của hàng "Lợi nhuận sau thuế" ngay bên dưới.
   */
  const rowBand = ROW_TOLERANCE;

  let best: { line: DocumentLine; index: number; dy: number; dx: number } | null = null;
  doc.lines.forEach((candidate, index) => {
    if (index === rowIndex) return;

    const dy = Math.abs(candidate.y - row.y);
    if (dy > rowBand) return;

    const dx = Math.abs(candidate.x - columnX);
    if (dx > tolerance) return;
    // Ô số phải thực sự chứa số.
    if (!/[\d]/.test(candidate.text)) return;

    // Đúng hàng trước đã, rồi mới tới đúng cột.
    if (!best || dy < best.dy || (dy === best.dy && dx < best.dx)) {
      best = { line: candidate, index, dy, dx };
    }
  });

  if (!best) return null;

  const picked = best as { line: DocumentLine; index: number; dx: number };
  const label = cleanLabel(row.text);

  return {
    id: `fact-${doc.kind}-${picked.index}`,
    label,
    value: picked.line.text.trim(),
    documentId: doc.id,
    documentTitle: doc.title,
    documentUrl: doc.url,
    region: toRegion(doc, picked.line, picked.index, label),
    quote: `${label}: ${picked.line.text.trim()}`,
  };
}

/** Tìm dòng chứa một cụm từ, trả về dữ kiện trỏ vào chính dòng đó. */
export function extractLineContaining(
  doc: DemoDocument,
  needle: string,
  label: string,
): ExtractedFact | null {
  const target = needle.toLowerCase();
  const index = doc.lines.findIndex((line) => line.text.toLowerCase().includes(target));
  if (index === -1) return null;

  const line = doc.lines[index];
  return {
    id: `fact-${doc.kind}-${index}`,
    label,
    value: line.text.trim(),
    documentId: doc.id,
    documentTitle: doc.title,
    documentUrl: doc.url,
    region: toRegion(doc, line, index, label),
    quote: line.text.trim(),
  };
}

/** Toàn bộ dữ kiện nhãn–giá trị bóc được từ mọi hồ sơ demo. */
export function readAllDocuments(): ExtractedFact[] {
  return DEMO_DOCUMENTS.flatMap((doc) => extractLabeledFacts(doc));
}

/** Tra dữ kiện theo nhãn (không phân biệt hoa thường, khớp chứa). */
export function findFact(facts: ExtractedFact[], labelNeedle: string): ExtractedFact | undefined {
  const target = labelNeedle.toLowerCase();
  return facts.find((fact) => fact.label.toLowerCase().includes(target));
}
