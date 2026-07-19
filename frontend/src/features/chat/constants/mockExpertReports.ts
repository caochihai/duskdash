import {
  findDocumentByKind,
  locateInDocument,
  type DemoDocument,
  type DocumentRegion,
} from './demoDocuments';
import type {
  ComposedReport,
  DomainReport,
  ExpertReportBundle,
  ReportCitation,
  ReportClaim,
} from '@/types/report';
import type { Customer, LoanApplication } from '@/types/customer';
import { formatCurrency } from '@/utils/formatCurrency';

/**
 * Đầu ra MOCK của 3 chuyên gia số — dựng theo đúng `libs/contracts/report.py`.
 *
 * Số liệu tài chính lấy từ bộ hồ sơ thật CR-A01 (`mock_6_credit_cases_full.json`),
 * dẫn chứng tài liệu trỏ về toạ độ OCR thật của ảnh scan. Nhờ vậy báo cáo đủ chi
 * tiết để một chuyên viên tín dụng ra được quyết định, và mọi con số đều lần
 * ngược được về nguồn.
 */

/* ------------------------------------------------------------------ */
/* Tiện ích dựng dẫn chứng                                             */
/* ------------------------------------------------------------------ */

/**
 * Sổ đăng ký vùng tài liệu đã được trích trong một lượt dựng báo cáo.
 * Nhờ nó, `documents` của bundle luôn chứa ĐÚNG những vùng mà báo cáo dẫn tới.
 */
const regionRegistry = new Map<string, { doc: DemoDocument; region: DocumentRegion }>();

/** Dẫn chứng trỏ vào tài liệu gốc. Không dò ra vị trí thì trả null (không bịa). */
function documentCitation(
  id: string,
  kind: DemoDocument['kind'],
  needle: string,
  label: string,
): ReportCitation | null {
  const doc = findDocumentByKind(kind);
  if (!doc) return null;

  const region = locateInDocument(doc.id, needle, label);
  if (!region) return null;

  regionRegistry.set(id, { doc, region });

  return {
    id,
    sourceType: 'DOCUMENT',
    quote: region.quote,
    locator: {
      documentId: doc.id,
      documentTitle: doc.title,
      documentUrl: doc.url,
      page: region.page,
      regionId: region.id,
    },
    confidence: 0.96,
  };
}

function policyCitation(id: string, clauseId: string, quote: string): ReportCitation {
  return { id, sourceType: 'POLICY', quote, policyClauseId: clauseId };
}

function recordCitation(id: string, recordRef: string, quote: string): ReportCitation {
  return { id, sourceType: 'RECORD', quote, recordRef };
}

function sqlCitation(id: string, sqlRef: string, quote: string): ReportCitation {
  return { id, sourceType: 'SQL', quote, sqlRef };
}

/** Loại bỏ dẫn chứng dò không ra, và loại luôn luận điểm mất hết nguồn. */
function pruneToSupported(
  citations: (ReportCitation | null)[],
  claims: ReportClaim[],
): { citations: ReportCitation[]; claims: ReportClaim[]; dropped: string[] } {
  const kept = citations.filter((item): item is ReportCitation => item !== null);
  const knownIds = new Set(kept.map((item) => item.id));
  const dropped: string[] = [];

  const survivingClaims = claims
    .map((claim) => ({
      ...claim,
      citationIds: claim.citationIds.filter((id) => knownIds.has(id)),
    }))
    .filter((claim) => {
      // Luận điểm suy luận được phép không có nguồn trực tiếp.
      if (claim.isInference) return true;
      if (claim.citationIds.length > 0) return true;
      dropped.push(claim.text);
      return false;
    });

  return { citations: kept, claims: survivingClaims, dropped };
}

/* ------------------------------------------------------------------ */
/* Số liệu thật của hồ sơ CR-A01 — Công ty CP Bao bì VinaNova          */
/* ------------------------------------------------------------------ */

const VINANOVA = {
  avgMonthlyInflow: 61_833_000_000,
  latestMonthInflow: 53_176_000_000,
  latestMonthOutflow: 51_528_000_000,
  avgBalance: 43_700_000_000,
  minBalance: 9_500_000_000,
  annualInflow: 742_000_000_000,
  annualOutflow: 719_000_000_000,
  currentRatio: 2.04,
  quickRatio: 1.5,
  debtToEquity: 0.36,
  dsoDays: 48,
  dioDays: 59,
  relatedRatio: 0.024,
  returnedCount: 0,
  overdraftDays: 0,
  negativeBalanceDays: 0,
  collateralMarket: 205_000_000_000,
  collateralRecovery: 145_000_000_000,
  ltvRecovery: 0.552,
  requestedLimit: 80_000_000_000,
  recommendedLimit: 80_000_000_000,
  pd12m: 0.008,
  riskGrade: 'A-',
  charterCapital: 160_000_000_000,
  foundedYear: 2014,
  representative: 'Nguyễn Hoàng Nam',
  documentCount: 11,
  monthsObserved: 12,
} as const;

/* ------------------------------------------------------------------ */
/* Chuyên gia 1 — TÀI CHÍNH                                            */
/* ------------------------------------------------------------------ */

function buildCreditReport(): DomainReport {
  const cashCycle = VINANOVA.dsoDays + VINANOVA.dioDays;

  const citations: (ReportCitation | null)[] = [
    sqlCitation(
      'cr-1',
      'banking.account_monthly_summary · 12 kỳ gần nhất',
      `Dòng tiền vào bình quân ${formatCurrency(VINANOVA.avgMonthlyInflow)}/tháng trên ${VINANOVA.monthsObserved} kỳ liên tiếp; kỳ gần nhất (2026-06) đạt ${formatCurrency(VINANOVA.latestMonthInflow)}.`,
    ),
    sqlCitation(
      'cr-2',
      'banking.account_monthly_summary · số dư',
      `Số dư bình quân ${formatCurrency(VINANOVA.avgBalance)}; số dư thấp nhất ${formatCurrency(VINANOVA.minBalance)}; ${VINANOVA.negativeBalanceDays} ngày âm số dư trong 12 tháng.`,
    ),
    sqlCitation(
      'cr-3',
      'banking.account_monthly_summary · cờ rủi ro',
      `${VINANOVA.returnedCount} giao dịch bị hoàn trả, ${VINANOVA.overdraftDays} ngày thấu chi trong kỳ quan sát.`,
    ),
    sqlCitation(
      'cr-4',
      'banking.transaction · bên liên quan',
      `Giao dịch với bên liên quan chiếm ${(VINANOVA.relatedRatio * 100).toFixed(1)}% tổng dòng tiền năm.`,
    ),
    recordCitation(
      'cr-5',
      'credit_case.metrics',
      `Current ratio ${VINANOVA.currentRatio}; quick ratio ${VINANOVA.quickRatio}; debt-to-equity ${VINANOVA.debtToEquity}.`,
    ),
    recordCitation(
      'cr-6',
      'credit_case.metrics · vòng quay',
      `DSO ${VINANOVA.dsoDays} ngày; DIO ${VINANOVA.dioDays} ngày.`,
    ),
    recordCitation(
      'cr-7',
      'credit_case.collateral',
      `Tài sản bảo đảm: giá thị trường ${formatCurrency(VINANOVA.collateralMarket)}, giá trị thu hồi ${formatCurrency(VINANOVA.collateralRecovery)}, LTV theo giá trị thu hồi ${(VINANOVA.ltvRecovery * 100).toFixed(1)}%.`,
    ),
    recordCitation(
      'cr-8',
      'credit_case · xếp hạng rủi ro',
      `Xác suất vỡ nợ 12 tháng (PD) ${(VINANOVA.pd12m * 100).toFixed(1)}%; hạng rủi ro ${VINANOVA.riskGrade}.`,
    ),
    documentCitation('cr-9', 'financial', 'KIỂM TOÁN', 'Báo cáo tài chính đã kiểm toán'),
  ];

  const claims: ReportClaim[] = [
    {
      id: 'cr-c1',
      text: `Dòng tiền kinh doanh ổn định và ở quy mô lớn: bình quân ${formatCurrency(VINANOVA.avgMonthlyInflow)}/tháng suốt ${VINANOVA.monthsObserved} tháng, tổng dòng vào năm đạt ${formatCurrency(VINANOVA.annualInflow)}.`,
      citationIds: ['cr-1'],
      tone: 'positive',
    },
    {
      id: 'cr-c2',
      text: `Thanh khoản lành mạnh: số dư bình quân ${formatCurrency(VINANOVA.avgBalance)}, số dư thấp nhất vẫn ${formatCurrency(VINANOVA.minBalance)}, không có ngày nào âm số dư.`,
      citationIds: ['cr-2'],
      tone: 'positive',
    },
    {
      id: 'cr-c3',
      text: `Không có dấu hiệu căng thẳng thanh toán: ${VINANOVA.returnedCount} giao dịch hoàn trả và ${VINANOVA.overdraftDays} ngày thấu chi trong toàn kỳ quan sát.`,
      citationIds: ['cr-3'],
      tone: 'positive',
    },
    {
      id: 'cr-c4',
      text: `Chỉ số cân đối ở mức an toàn: current ratio ${VINANOVA.currentRatio} (ngưỡng tham chiếu 1,2), quick ratio ${VINANOVA.quickRatio}, đòn bẩy D/E ${VINANOVA.debtToEquity} — thấp hơn nhiều mức cảnh báo 2,0.`,
      citationIds: ['cr-5'],
      tone: 'positive',
    },
    {
      id: 'cr-c5',
      text: `Chu kỳ tiền mặt khoảng ${cashCycle} ngày (DSO ${VINANOVA.dsoDays} + DIO ${VINANOVA.dioDays}), tương đối dài so với ngành bao bì — đây chính là lý do phát sinh nhu cầu vốn lưu động.`,
      citationIds: ['cr-6'],
      isInference: true,
      tone: 'neutral',
    },
    {
      id: 'cr-c6',
      text: `Giao dịch với bên liên quan chỉ chiếm ${(VINANOVA.relatedRatio * 100).toFixed(1)}% tổng dòng tiền, dưới xa ngưỡng chú ý 10% — rủi ro dòng tiền vòng vo thấp.`,
      citationIds: ['cr-4'],
      tone: 'positive',
    },
    {
      id: 'cr-c7',
      text: `Tài sản bảo đảm định giá thu hồi ${formatCurrency(VINANOVA.collateralRecovery)}; với hạn mức đề nghị ${formatCurrency(VINANOVA.requestedLimit)}, LTV theo giá trị thu hồi là ${(VINANOVA.ltvRecovery * 100).toFixed(1)}%, còn dư địa so với trần 80%.`,
      citationIds: ['cr-7'],
      tone: 'positive',
    },
    {
      id: 'cr-c8',
      text: `Xác suất vỡ nợ 12 tháng ${(VINANOVA.pd12m * 100).toFixed(1)}%, xếp hạng ${VINANOVA.riskGrade} — thuộc nhóm rủi ro thấp theo thang nội bộ.`,
      citationIds: ['cr-8'],
      tone: 'positive',
    },
    {
      id: 'cr-c9',
      text: 'Báo cáo tài chính đã được kiểm toán bởi đơn vị độc lập, làm tăng độ tin cậy của số liệu do khách hàng cung cấp.',
      citationIds: ['cr-9'],
      tone: 'positive',
    },
    {
      id: 'cr-c10',
      text: `Điểm cần lưu ý: dòng tiền tháng 2026-06 giảm về ${formatCurrency(VINANOVA.latestMonthInflow)} so với bình quân ${formatCurrency(VINANOVA.avgMonthlyInflow)} — mức giảm khoảng 14%. Cần xác nhận đây là yếu tố mùa vụ hay xu hướng.`,
      citationIds: ['cr-1'],
      isInference: true,
      tone: 'warning',
    },
  ];

  const pruned = pruneToSupported(citations, claims);

  return {
    domain: 'CREDIT',
    agent: 'credit-specialist',
    status: 'OK',
    summary: `Năng lực tài chính đủ mạnh để chịu hạn mức ${formatCurrency(VINANOVA.requestedLimit)}: dòng tiền lớn và đều, thanh khoản tốt, đòn bẩy thấp, tài sản bảo đảm dư dả. Một điểm cần làm rõ là dòng tiền tháng gần nhất giảm ~14%.`,
    claims: pruned.claims,
    citations: pruned.citations,
    confidence: 0.88,
  };
}

/* ------------------------------------------------------------------ */
/* Chuyên gia 2 — PHÁP LÝ & TUÂN THỦ                                   */
/* ------------------------------------------------------------------ */

function buildLegalReport(): DomainReport {
  const citations: (ReportCitation | null)[] = [
    documentCitation('lg-1', 'legal', 'SỞ KẾ HOẠCH VÀ ĐẦU TƯ', 'Cơ quan cấp đăng ký doanh nghiệp'),
    documentCitation('lg-2', 'profile', 'Vốn điều lệ', 'Vốn điều lệ đăng ký'),
    documentCitation('lg-3', 'profile', 'Người đại diện', 'Người đại diện theo pháp luật'),
    recordCitation(
      'lg-4',
      'customer · sàng lọc tuân thủ',
      'KYC: CLEAR. AML: CLEAR. Sàng lọc danh sách chế tài: NO_MATCH. Cờ PEP: không.',
    ),
    policyCitation(
      'lg-5',
      'CREDIT-POLICY-3.2',
      'DSCR tối thiểu cho khoản vay bổ sung vốn lưu động là 1.25.',
    ),
    policyCitation(
      'lg-6',
      'CREDIT-POLICY-4.1',
      'Tỷ lệ cho vay trên tài sản bảo đảm (LTV) không vượt 80% đối với bất động sản.',
    ),
    policyCitation(
      'lg-7',
      'AML-POLICY-2.4',
      'Bắt buộc hoàn tất sàng lọc AML/PEP và lưu hồ sơ KYC trước khi giải ngân.',
    ),
    recordCitation(
      'lg-8',
      'credit_case.profile',
      `Loại hình: công ty cổ phần. Năm thành lập: ${VINANOVA.foundedYear}. Ngành: sản xuất bao bì giấy, bao bì nhựa và in công nghiệp.`,
    ),
  ];

  const claims: ReportClaim[] = [
    {
      id: 'lg-c1',
      text: `Tư cách pháp nhân hợp lệ: doanh nghiệp được Sở Kế hoạch và Đầu tư cấp đăng ký, hoạt động từ năm ${VINANOVA.foundedYear} đến nay (${2026 - VINANOVA.foundedYear} năm).`,
      citationIds: ['lg-1', 'lg-8'],
      tone: 'positive',
    },
    {
      id: 'lg-c2',
      text: `Vốn điều lệ đăng ký ${formatCurrency(VINANOVA.charterCapital)}, tương đương 2 lần hạn mức tín dụng đề nghị — quy mô vốn chủ tương xứng với khoản vay.`,
      citationIds: ['lg-2'],
      tone: 'positive',
    },
    {
      id: 'lg-c3',
      text: `Người đại diện theo pháp luật: ${VINANOVA.representative}. Thông tin trên hồ sơ khớp với đăng ký doanh nghiệp.`,
      citationIds: ['lg-3'],
      tone: 'positive',
    },
    {
      id: 'lg-c4',
      text: 'Sàng lọc tuân thủ đạt toàn bộ: KYC hợp lệ, AML không phát hiện, không trùng danh sách chế tài, không thuộc diện PEP.',
      citationIds: ['lg-4'],
      tone: 'positive',
    },
    {
      id: 'lg-c5',
      text: `Đối chiếu CREDIT-POLICY-4.1: LTV theo giá trị thu hồi ${(VINANOVA.ltvRecovery * 100).toFixed(1)}% nằm trong trần 80% — điều kiện tài sản bảo đảm ĐẠT.`,
      citationIds: ['lg-6'],
      tone: 'positive',
    },
    {
      id: 'lg-c6',
      text: 'Đối chiếu CREDIT-POLICY-3.2 (DSCR tối thiểu 1.25): hồ sơ chưa có phương án trả nợ chi tiết theo kỳ, nên chưa tính được DSCR chính thức. Cần bổ sung trước khi trình phê duyệt.',
      citationIds: ['lg-5'],
      tone: 'warning',
    },
    {
      id: 'lg-c7',
      text: 'Đối chiếu AML-POLICY-2.4: hồ sơ KYC đã lưu và sàng lọc đã hoàn tất, đủ điều kiện tuân thủ để giải ngân.',
      citationIds: ['lg-7', 'lg-4'],
      tone: 'positive',
    },
  ];

  const pruned = pruneToSupported(citations, claims);

  return {
    domain: 'LEGAL',
    agent: 'legal-specialist',
    status: 'PARTIAL',
    summary:
      'Tư cách pháp nhân và tuân thủ AML/KYC đều đạt. Điều kiện LTV thoả chính sách. Vướng mắc duy nhất: chưa đủ dữ liệu để tính DSCR theo CREDIT-POLICY-3.2.',
    claims: pruned.claims,
    citations: pruned.citations,
    confidence: 0.82,
    note: 'Thiếu phương án trả nợ chi tiết nên chưa kiểm chứng được điều kiện DSCR.',
  };
}

/* ------------------------------------------------------------------ */
/* Chuyên gia 3 — HỒ SƠ & CHỨNG TỪ                                     */
/* ------------------------------------------------------------------ */

function buildDocumentReport(): DomainReport {
  const citations: (ReportCitation | null)[] = [
    sqlCitation(
      'dc-1',
      'document · trạng thái OCR',
      `Đã nhận ${VINANOVA.documentCount} tài liệu; OCR thành công ${VINANOVA.documentCount}/${VINANOVA.documentCount}; không có tài liệu lỗi đọc.`,
    ),
    documentCitation(
      'dc-2',
      'profile',
      'PHIẾU THÔNG TIN KHÁCH HÀNG DOANH NGHIỆP',
      'Phiếu thông tin khách hàng',
    ),
    documentCitation('dc-3', 'legal', 'SỞ KẾ HOẠCH VÀ ĐẦU TƯ', 'Giấy chứng nhận đăng ký doanh nghiệp'),
    documentCitation('dc-4', 'financial', 'KIỂM TOÁN', 'Báo cáo kiểm toán độc lập'),
    documentCitation('dc-5', 'profile', 'Vốn điều lệ', 'Vốn điều lệ trên hồ sơ'),
    sqlCitation(
      'dc-6',
      'document · đối chiếu danh mục',
      'Danh mục chứng từ bắt buộc cho sản phẩm tài trợ vốn lưu động: 9 mục. Đã có 8 mục. Thiếu: hợp đồng đầu ra chứng minh mục đích sử dụng vốn.',
    ),
  ];

  const claims: ReportClaim[] = [
    {
      id: 'dc-c1',
      text: `Toàn bộ ${VINANOVA.documentCount} tài liệu khách hàng nộp đã được số hoá và đọc thành công, đủ điều kiện để đối chiếu tự động.`,
      citationIds: ['dc-1'],
      tone: 'positive',
    },
    {
      id: 'dc-c2',
      text: 'Phiếu thông tin khách hàng doanh nghiệp có đầy đủ và khớp với dữ liệu định danh trong hệ thống.',
      citationIds: ['dc-2'],
      tone: 'positive',
    },
    {
      id: 'dc-c3',
      text: 'Giấy chứng nhận đăng ký doanh nghiệp do cơ quan có thẩm quyền cấp, còn hiệu lực.',
      citationIds: ['dc-3'],
      tone: 'positive',
    },
    {
      id: 'dc-c4',
      text: 'Có báo cáo tài chính kèm ý kiến kiểm toán độc lập — đáp ứng yêu cầu chứng từ tài chính của sản phẩm.',
      citationIds: ['dc-4'],
      tone: 'positive',
    },
    {
      id: 'dc-c5',
      text: `Đối chiếu chéo vốn điều lệ: con số ghi trên hồ sơ giấy khớp với ${formatCurrency(VINANOVA.charterCapital)} trong hệ thống — không phát hiện sai lệch.`,
      citationIds: ['dc-5'],
      tone: 'positive',
    },
    {
      id: 'dc-c6',
      text: 'THIẾU CHỨNG TỪ: hồ sơ đạt 8/9 mục bắt buộc. Còn thiếu hợp đồng đầu ra chứng minh mục đích sử dụng vốn — đây là điều kiện bắt buộc trước giải ngân.',
      citationIds: ['dc-6'],
      tone: 'warning',
    },
  ];

  const pruned = pruneToSupported(citations, claims);

  return {
    domain: 'DOCUMENT',
    agent: 'document-specialist',
    status: 'PARTIAL',
    summary: `Đã đọc trọn ${VINANOVA.documentCount} tài liệu, các chứng từ pháp lý và tài chính cốt lõi đều có và khớp dữ liệu hệ thống. Hồ sơ đạt 8/9 mục bắt buộc, thiếu hợp đồng đầu ra.`,
    claims: pruned.claims,
    citations: pruned.citations,
    confidence: 0.9,
    note: 'Thiếu 1 chứng từ bắt buộc: hợp đồng đầu ra chứng minh mục đích sử dụng vốn.',
  };
}

/* ------------------------------------------------------------------ */
/* Tổng hợp — bản trình chuyên viên ra quyết định                      */
/* ------------------------------------------------------------------ */

function buildComposed(question: string, reports: DomainReport[]): ComposedReport {
  const byDomain = (domain: DomainReport["domain"]) =>
    reports.find((report) => report.domain === domain);

  const credit = byDomain('CREDIT');
  const legal = byDomain('LEGAL');
  const document = byDomain('DOCUMENT');

  /** Chỉ lấy lại luận điểm CÓ THẬT từ báo cáo gốc — không viết luận điểm mới. */
  const pick = (report: DomainReport | undefined, ids: string[]): ReportClaim[] =>
    (report?.claims ?? []).filter((claim) => ids.includes(claim.id));

  return {
    question,
    decision: 'APPROVE_WITH_CONDITIONS',
    recommendation:
      `Đề xuất PHÊ DUYỆT hạn mức ${formatCurrency(VINANOVA.recommendedLimit)} KÈM ĐIỀU KIỆN. ` +
      `Năng lực tài chính và tài sản bảo đảm đều vượt yêu cầu (LTV ${(VINANOVA.ltvRecovery * 100).toFixed(1)}% so với trần 80%, ` +
      `PD 12 tháng ${(VINANOVA.pd12m * 100).toFixed(1)}%, hạng ${VINANOVA.riskGrade}). ` +
      'Hai vướng mắc đều thuộc nhóm bổ sung được, không phải vấn đề bản chất tín dụng: ' +
      'thiếu hợp đồng đầu ra và chưa tính được DSCR.',
    sections: [
      {
        title: 'Năng lực tài chính',
        domain: 'CREDIT',
        claims: pick(credit, ['cr-c1', 'cr-c2', 'cr-c4', 'cr-c7', 'cr-c8', 'cr-c10']),
      },
      {
        title: 'Pháp lý và tuân thủ',
        domain: 'LEGAL',
        claims: pick(legal, ['lg-c1', 'lg-c4', 'lg-c5', 'lg-c6']),
      },
      {
        title: 'Tính đầy đủ hồ sơ',
        domain: 'DOCUMENT',
        claims: pick(document, ['dc-c1', 'dc-c5', 'dc-c6']),
      },
    ],
    conditions: [
      'Bổ sung hợp đồng đầu ra chứng minh mục đích sử dụng vốn (chứng từ bắt buộc còn thiếu).',
      'Cung cấp phương án trả nợ chi tiết theo kỳ để tính DSCR, đối chiếu ngưỡng tối thiểu 1.25 theo CREDIT-POLICY-3.2.',
      'Giải trình mức giảm ~14% dòng tiền vào của kỳ 2026-06 so với bình quân 12 tháng.',
      'Hoàn tất đăng ký giao dịch bảo đảm trước khi giải ngân lần đầu.',
    ],
    domainStatus: {
      CREDIT: credit?.status ?? 'FAILED',
      LEGAL: legal?.status ?? 'FAILED',
      DOCUMENT: document?.status ?? 'FAILED',
    },
    warnings: [
      'Lĩnh vực LEGAL và DOCUMENT chỉ có kết quả một phần — xem mục điều kiện kèm theo.',
    ],
  };
}

/* ------------------------------------------------------------------ */
/* Điểm vào                                                            */
/* ------------------------------------------------------------------ */

/**
 * Báo cáo đầy đủ cho hồ sơ có bộ chứng từ đã số hoá (VinaNova).
 * Khách hàng khác chưa số hoá hồ sơ nên KHÔNG dựng báo cáo dạng này —
 * thà không có báo cáo còn hơn có báo cáo không dẫn được nguồn.
 */
export function buildExpertReports(
  question: string,
  customer: Customer,
  application: LoanApplication,
): ExpertReportBundle | null {
  if (customer.id !== 'cus-003') return null;
  void application;

  regionRegistry.clear();
  const domainReports = [buildCreditReport(), buildLegalReport(), buildDocumentReport()];

  // Gom vùng theo từng tài liệu, khử trùng theo id vùng.
  const byDocument = new Map<string, { name: string; url: string; regions: DocumentRegion[] }>();
  for (const { doc, region } of regionRegistry.values()) {
    const entry = byDocument.get(doc.id) ?? { name: doc.title, url: doc.url, regions: [] };
    if (!entry.regions.some((item) => item.id === region.id)) entry.regions.push(region);
    byDocument.set(doc.id, entry);
  }

  return {
    composed: buildComposed(question, domainReports),
    domainReports,
    documents: [...byDocument.values()],
  };
}
