import type { SourceLocator } from './source';
import type { DocumentRegion } from '@/features/chat/constants/demoDocuments';

/**
 * Báo cáo của chuyên gia số — PHẢN CHIẾU ĐÚNG hợp đồng backend
 * (`libs/contracts/report.py` + `citation.py`).
 *
 * Giữ đúng hình dạng này là một trong ba rủi ro đã khoá của dự án: "mock = hợp
 * đồng thật". Khi cắm Engine thật vào, giao diện không phải sửa.
 *
 * Bất biến bắt buộc (chống bịa nguồn):
 * - Mọi `citationIds` của một luận điểm PHẢI khớp `ReportCitation.id` có thật
 *   trong `citations` của chính báo cáo đó.
 * - Citation kiểu DOCUMENT BẮT BUỘC có `locator` để giao diện highlight được.
 */

export type ReportDomain = 'CREDIT' | 'LEGAL' | 'DOCUMENT';

export const REPORT_DOMAIN_LABEL: Record<ReportDomain, string> = {
  CREDIT: 'Tài chính',
  LEGAL: 'Pháp lý & Tuân thủ',
  DOCUMENT: 'Hồ sơ & Chứng từ',
};

export type ReportStatus = 'OK' | 'PARTIAL' | 'FAILED';

export const REPORT_STATUS_LABEL: Record<ReportStatus, string> = {
  OK: 'Hoàn tất',
  PARTIAL: 'Thiếu dữ liệu một phần',
  FAILED: 'Không chạy được',
};

/** Loại nguồn — quyết định cách giao diện mở dẫn chứng. */
export type CitationSourceType = 'DOCUMENT' | 'POLICY' | 'RECORD' | 'SQL';

export const CITATION_SOURCE_LABEL: Record<CitationSourceType, string> = {
  DOCUMENT: 'Tài liệu gốc',
  POLICY: 'Điều khoản chính sách',
  RECORD: 'Bản ghi hệ thống',
  SQL: 'Truy vấn dữ liệu',
};

export interface ReportCitation {
  id: string;
  sourceType: CitationSourceType;
  /** Đoạn nguyên văn được trích — hiện nguyên si, không diễn giải lại. */
  quote: string;
  /** Có mặt khi sourceType = DOCUMENT: mở hồ sơ và khoanh đỏ đúng vùng. */
  locator?: SourceLocator;
  /** Có mặt khi sourceType = POLICY, ví dụ "CREDIT-POLICY-3.2". */
  policyClauseId?: string;
  /** Có mặt khi sourceType = RECORD: bảng/bản ghi trong hệ thống. */
  recordRef?: string;
  /** Có mặt khi sourceType = SQL: mô tả truy vấn đã chạy. */
  sqlRef?: string;
  confidence?: number;
}

export interface ReportClaim {
  id: string;
  text: string;
  /** Nguồn của luận điểm này. Rỗng + isInference=false là vi phạm bất biến. */
  citationIds: string[];
  /**
   * Luận điểm SUY LUẬN từ các nguồn khác, không đọc thẳng từ một nguồn.
   * Giao diện đánh dấu riêng để chuyên viên biết đâu là dữ kiện, đâu là suy diễn.
   */
  isInference?: boolean;
  /** Ảnh hưởng tới quyết định: thuận lợi / cảnh báo / trung tính. */
  tone?: 'positive' | 'warning' | 'neutral';
}

export interface DomainReport {
  domain: ReportDomain;
  /** Tên tác nhân đã tạo báo cáo, phục vụ ghi vết. */
  agent: string;
  status: ReportStatus;
  summary: string;
  claims: ReportClaim[];
  citations: ReportCitation[];
  confidence: number;
  /** Lý do khi status khác OK. */
  note?: string;
}

export interface ComposedSection {
  title: string;
  domain?: ReportDomain;
  claims: ReportClaim[];
}

/** Kết luận tổng hợp trình chuyên viên — đã verify chống bịa nguồn. */
export interface ComposedReport {
  question: string;
  /** Đề xuất hành động, viết cho người ra quyết định đọc. */
  recommendation: string;
  decision: 'APPROVE' | 'APPROVE_WITH_CONDITIONS' | 'DECLINE' | 'NEED_MORE_INFO';
  sections: ComposedSection[];
  /** Điều kiện phải hoàn tất trước khi giải ngân. */
  conditions?: string[];
  /** Luận điểm bị loại vì không resolve được nguồn — hiện minh bạch, không giấu. */
  unsupportedClaims?: string[];
  domainStatus: Record<ReportDomain, ReportStatus>;
  warnings?: string[];
}

/** Gói đầy đủ: 3 báo cáo chuyên gia + kết luận tổng hợp. */
export interface ExpertReportBundle {
  composed: ComposedReport;
  domainReports: DomainReport[];
  /**
   * Hồ sơ kèm TOÀN BỘ vùng được các báo cáo trích dẫn.
   *
   * Phải dựng từ chính citation của báo cáo: nếu lấy từ nguồn khác, một trích dẫn
   * có thể trỏ tới vùng không nằm trong danh sách và giao diện mở hồ sơ ra nhưng
   * không khoanh được chỗ nào.
   */
  documents: {
    name: string;
    url: string;
    regions: DocumentRegion[];
  }[];
}

export const DECISION_LABEL: Record<ComposedReport['decision'], string> = {
  APPROVE: 'Đề xuất phê duyệt',
  APPROVE_WITH_CONDITIONS: 'Đề xuất phê duyệt có điều kiện',
  DECLINE: 'Đề xuất từ chối',
  NEED_MORE_INFO: 'Cần bổ sung thông tin',
};

/**
 * Kiểm tra bất biến chống bịa nguồn cho một báo cáo lĩnh vực.
 * Trả về danh sách citationId bị trích nhưng không tồn tại (rỗng = hợp lệ).
 */
export function findDanglingCitations(report: DomainReport): string[] {
  const known = new Set(report.citations.map((citation) => citation.id));
  const dangling: string[] = [];

  for (const claim of report.claims) {
    for (const id of claim.citationIds) {
      if (!known.has(id)) dangling.push(id);
    }
  }
  return dangling;
}
