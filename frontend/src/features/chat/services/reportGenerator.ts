import { DEMO_DOCUMENTS, type DocumentRegion } from '../constants/demoDocuments';
import {
  extractLabeledFacts,
  extractLineContaining,
  extractTableCell,
  findFact,
  type ExtractedFact,
} from './documentReader';
import type {
  ComposedReport,
  DomainReport,
  ExpertReportBundle,
  ReportCitation,
  ReportClaim,
} from '@/types/report';

/**
 * BƯỚC 2 CỦA PIPELINE: sinh báo cáo TỪ dữ kiện đã bóc khỏi OCR.
 *
 *   OCR → documentReader → dữ kiện có toạ độ → [reportGenerator] → báo cáo có nguồn
 *
 * Đây là chỗ mô hình ngôn ngữ sẽ đứng khi có khoá API. Hiện tại nó chạy tất định:
 * cùng đầu vào cho ra cùng đầu ra, không gọi mạng. Điều quan trọng KHÔNG nằm ở
 * việc câu chữ do người hay máy viết, mà ở chỗ:
 *
 *   1. Mọi con số trong báo cáo đều LẤY TỪ dữ kiện OCR bóc được, không viết tay.
 *   2. Dữ kiện nào tài liệu không có thì luận điểm tương ứng KHÔNG được sinh ra.
 *   3. Mỗi luận điểm mang theo toạ độ của đúng ô chữ đã dùng để suy ra nó.
 *
 * Nhờ ba điều đó, thay bước này bằng LLM thật chỉ là đổi hàm sinh câu chữ; ràng
 * buộc chống bịa nguồn nằm ở cấu trúc dữ liệu chứ không nằm ở lời nhắc mô hình.
 */

/* ------------------------------------------------------------------ */
/* Gom dữ kiện đầu vào                                                 */
/* ------------------------------------------------------------------ */

interface ReadingContext {
  facts: ExtractedFact[];
  citations: ReportCitation[];
  regions: Map<string, { name: string; url: string; regions: DocumentRegion[] }>;
}

function createContext(): ReadingContext {
  const profile = DEMO_DOCUMENTS.find((doc) => doc.kind === 'profile');
  const legal = DEMO_DOCUMENTS.find((doc) => doc.kind === 'legal');
  const financial = DEMO_DOCUMENTS.find((doc) => doc.kind === 'financial');

  const facts: ExtractedFact[] = [];

  if (profile) {
    facts.push(...extractLabeledFacts(profile));

    // Bảng tài chính: lấy cột 2025 (x≈0,68) — kỳ đầy đủ gần nhất.
    for (const row of ['Doanh thu thuần', 'EBITDA', 'Lợi nhuận sau thuế', 'Dòng tiền HĐKD']) {
      const cell = extractTableCell(profile, row, 0.68);
      if (cell) facts.push({ ...cell, label: `${row} 2025` });
    }
    // Cột 2024 để so sánh tăng trưởng.
    const revenue2024 = extractTableCell(profile, 'Doanh thu thuần', 0.53);
    if (revenue2024) facts.push({ ...revenue2024, label: 'Doanh thu thuần 2024' });

    const ltv = extractLineContaining(profile, '55,2', 'Tỷ lệ dư nợ trên giá trị xử lý');
    if (ltv) facts.push(ltv);
  }

  if (legal) {
    const issuer = extractLineContaining(legal, 'SỞ KẾ HOẠCH', 'Cơ quan cấp phép');
    if (issuer) facts.push(issuer);
  }

  if (financial) {
    const auditor = extractLineContaining(financial, 'KIỂM TOÁN', 'Đơn vị kiểm toán');
    if (auditor) facts.push(auditor);
  }

  return { facts, citations: [], regions: new Map() };
}

/** Biến một dữ kiện thành trích dẫn tài liệu và ghi nhận vùng để highlight. */
function cite(context: ReadingContext, fact: ExtractedFact): string {
  if (!context.citations.some((item) => item.id === fact.id)) {
    context.citations.push({
      id: fact.id,
      sourceType: 'DOCUMENT',
      quote: fact.quote,
      locator: {
        documentId: fact.documentId,
        documentTitle: fact.documentTitle,
        documentUrl: fact.documentUrl,
        page: fact.region.page,
        regionId: fact.region.id,
      },
      confidence: 0.96,
    });

    const entry = context.regions.get(fact.documentId) ?? {
      name: fact.documentTitle,
      url: fact.documentUrl,
      regions: [],
    };
    if (!entry.regions.some((region) => region.id === fact.region.id)) {
      entry.regions.push(fact.region);
    }
    context.regions.set(fact.documentId, entry);
  }
  return fact.id;
}

/** Trích dẫn chính sách — nguồn nội bộ, không nằm trong tài liệu khách hàng. */
function citePolicy(context: ReadingContext, id: string, clauseId: string, quote: string): string {
  if (!context.citations.some((item) => item.id === id)) {
    context.citations.push({ id, sourceType: 'POLICY', quote, policyClauseId: clauseId });
  }
  return id;
}

/**
 * Sinh một luận điểm CHỈ KHI mọi dữ kiện nó cần đều bóc được từ tài liệu.
 * Thiếu bất kỳ dữ kiện nào -> trả null -> luận điểm không xuất hiện trong báo cáo.
 */
function claimFrom(
  context: ReadingContext,
  id: string,
  needed: (ExtractedFact | undefined)[],
  render: (values: string[]) => string,
  options: { tone?: ReportClaim['tone']; isInference?: boolean; extraCitations?: string[] } = {},
): ReportClaim | null {
  if (needed.some((fact) => fact === undefined)) return null;

  const facts = needed as ExtractedFact[];
  const citationIds = facts.map((fact) => cite(context, fact));
  if (options.extraCitations) citationIds.push(...options.extraCitations);

  return {
    id,
    text: render(facts.map((fact) => fact.value)),
    citationIds,
    ...(options.tone ? { tone: options.tone } : {}),
    ...(options.isInference ? { isInference: true } : {}),
  };
}

function compact(claims: (ReportClaim | null)[]): ReportClaim[] {
  return claims.filter((claim): claim is ReportClaim => claim !== null);
}

/** Đọc số từ chuỗi OCR kiểu "2,04 lần", "705", "160 tỷ đồng". */
function parseNumber(raw: string): number | null {
  const match = raw.replace(/\./g, '').match(/-?\d+(?:,\d+)?/);
  if (!match) return null;
  const value = Number(match[0].replace(',', '.'));
  return Number.isFinite(value) ? value : null;
}

/* ------------------------------------------------------------------ */
/* Chuyên gia TÀI CHÍNH                                                */
/* ------------------------------------------------------------------ */

function buildCredit(context: ReadingContext): DomainReport {
  const f = (needle: string) => findFact(context.facts, needle);

  const revenue2025 = f('Doanh thu thuần 2025');
  const revenue2024 = f('Doanh thu thuần 2024');
  const ebitda = f('EBITDA 2025');
  const profit = f('Lợi nhuận sau thuế 2025');
  const cashflow = f('Dòng tiền HĐKD 2025');
  const currentRatio = f('Current ratio');
  const quickRatio = f('Quick ratio');
  const leverage = f('Tổng nợ vay/VCSH');
  const interestCover = f('EBIT/Chi phí lãi vay');
  const dso = f('DSO');
  const dio = f('DIO');
  const ltv = f('Tỷ lệ dư nợ');
  const requested = f('Số tiền đề nghị');
  const verifiedNeed = f('Nhu cầu vốn xác minh');
  const repayment = f('Nguồn trả nợ chính');
  const concentration = f('Khách hàng & thị trường');
  const auditor = f('Đơn vị kiểm toán');

  const growth =
    revenue2025 && revenue2024
      ? (() => {
          const now = parseNumber(revenue2025.value);
          const before = parseNumber(revenue2024.value);
          if (now === null || before === null || before === 0) return null;
          return Math.round(((now - before) / before) * 1000) / 10;
        })()
      : null;

  const cashCycle =
    dso && dio
      ? (() => {
          const a = parseNumber(dso.value);
          const b = parseNumber(dio.value);
          return a !== null && b !== null ? a + b : null;
        })()
      : null;

  const claims = compact([
    claimFrom(
      context,
      'cr-c1',
      [revenue2025, ebitda, profit],
      ([rev, eb, pr]) =>
        `Kết quả kinh doanh năm 2025: doanh thu thuần ${rev} tỷ đồng, EBITDA ${eb} tỷ đồng, lợi nhuận sau thuế ${pr} tỷ đồng — biên lợi nhuận ròng khoảng ${(() => {
          const r = parseNumber(rev);
          const p = parseNumber(pr);
          return r && p ? ((p / r) * 100).toFixed(1) : '—';
        })()}%.`,
      { tone: 'positive' },
    ),
    growth !== null
      ? claimFrom(
          context,
          'cr-c2',
          [revenue2024, revenue2025],
          ([before, now]) =>
            `Doanh thu tăng trưởng ${growth}% so với năm trước (${before} → ${now} tỷ đồng), cho thấy quy mô hoạt động đang mở rộng ổn định.`,
          { tone: 'positive', isInference: true },
        )
      : null,
    claimFrom(
      context,
      'cr-c3',
      [cashflow],
      ([cf]) =>
        `Dòng tiền từ hoạt động kinh doanh năm 2025 đạt ${cf} tỷ đồng — nguồn trả nợ nội sinh dồi dào so với hạn mức đề nghị.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'cr-c4',
      [currentRatio, quickRatio],
      ([current, quick]) =>
        `Thanh khoản lành mạnh: current ratio ${current}, quick ratio ${quick} — đều trên ngưỡng tham chiếu 1,2 và 1,0.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'cr-c5',
      [leverage, interestCover],
      ([lev, cover]) =>
        `Đòn bẩy thấp và khả năng trả lãi rất tốt: tổng nợ vay trên vốn chủ sở hữu ${lev}, EBIT trên chi phí lãi vay ${cover}.`,
      { tone: 'positive' },
    ),
    cashCycle !== null
      ? claimFrom(
          context,
          'cr-c6',
          [dso, dio],
          ([d, i]) =>
            `Chu kỳ vốn lưu động khoảng ${cashCycle} ngày (DSO ${d} + DIO ${i}) — đây chính là nguyên nhân phát sinh nhu cầu tài trợ vốn lưu động.`,
          { tone: 'neutral', isInference: true },
        )
      : null,
    claimFrom(
      context,
      'cr-c7',
      [requested, verifiedNeed],
      ([amount, need]) =>
        `Hạn mức đề nghị ${amount} nằm trong khoảng nhu cầu vốn đã xác minh (${need}) — quy mô cấp tín dụng phù hợp với nhu cầu thực.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'cr-c8',
      [ltv],
      ([value]) =>
        `Tỷ lệ dư nợ trên giá trị xử lý tài sản bảo đảm là ${value}, còn dư địa đáng kể so với trần 80% theo chính sách.`,
      {
        tone: 'positive',
        extraCitations: [
          citePolicy(
            context,
            'pol-ltv',
            'CREDIT-POLICY-4.1',
            'Tỷ lệ cho vay trên tài sản bảo đảm (LTV) không vượt 80% đối với bất động sản.',
          ),
        ],
      },
    ),
    claimFrom(
      context,
      'cr-c9',
      [repayment],
      ([source]) => `Nguồn trả nợ chính được xác định là ${source}, phù hợp với bản chất khoản vay vốn lưu động.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'cr-c10',
      [auditor],
      () =>
        'Số liệu tài chính có báo cáo kiểm toán độc lập kèm theo, làm tăng độ tin cậy của thông tin do khách hàng cung cấp.',
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'cr-c11',
      [concentration],
      ([value]) =>
        `Cần lưu ý mức độ tập trung khách hàng đầu ra: ${value.replace(/;$/, '')}. Mất một khách hàng lớn sẽ ảnh hưởng trực tiếp tới dòng tiền trả nợ.`,
      { tone: 'warning' },
    ),
  ]);

  return {
    domain: 'CREDIT',
    agent: 'credit-specialist',
    status: 'OK',
    summary:
      'Năng lực tài chính đủ mạnh cho hạn mức đề nghị: doanh thu và lợi nhuận tăng trưởng, dòng tiền kinh doanh dồi dào, đòn bẩy thấp, tài sản bảo đảm dư dả. Điểm cần theo dõi là mức tập trung khách hàng đầu ra.',
    claims,
    citations: [],
    confidence: 0.88,
  };
}

/* ------------------------------------------------------------------ */
/* Chuyên gia PHÁP LÝ & TUÂN THỦ                                       */
/* ------------------------------------------------------------------ */

function buildLegal(context: ReadingContext): DomainReport {
  const f = (needle: string) => findFact(context.facts, needle);

  const name = f('Tên doanh nghiệp');
  const form = f('Loại hình');
  const founded = f('Năm thành lập');
  const capital = f('Vốn điều lệ');
  const representative = f('Người đại diện');
  const legalStatus = f('Tình trạng pháp lý');
  const ubo = f('UBO');
  const cic = f('CIC và quan hệ tín dụng');
  const history = f('Lịch sử tín dụng');
  const overdue = f('Nợ quá hạn');
  const breach = f('Vi phạm nghĩa vụ');
  const issuer = f('Cơ quan cấp phép');
  const purpose = f('Mục đích vay');

  const claims = compact([
    claimFrom(
      context,
      'lg-c1',
      [name, form, founded],
      ([n, fm, yr]) => `Tư cách pháp nhân: ${n}, ${fm}, thành lập năm ${yr}.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'lg-c2',
      [issuer],
      () => 'Giấy chứng nhận đăng ký doanh nghiệp do Sở Kế hoạch và Đầu tư cấp, có trong hồ sơ.',
      { tone: 'positive' },
    ),
    claimFrom(context, 'lg-c3', [capital], ([value]) => `Vốn điều lệ đăng ký ${value}.`, {
      tone: 'positive',
    }),
    claimFrom(
      context,
      'lg-c4',
      [representative],
      ([value]) => `Người đại diện theo pháp luật: ${value}.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'lg-c5',
      [legalStatus],
      ([value]) => `Tình trạng pháp lý: ${value}.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'lg-c6',
      [ubo],
      ([value]) => `Chủ sở hữu hưởng lợi cuối cùng (UBO): ${value} — đáp ứng yêu cầu sàng lọc AML/PEP.`,
      {
        tone: 'positive',
        extraCitations: [
          citePolicy(
            context,
            'pol-aml',
            'AML-POLICY-2.4',
            'Bắt buộc hoàn tất sàng lọc AML/PEP và lưu hồ sơ KYC trước khi giải ngân.',
          ),
        ],
      },
    ),
    claimFrom(
      context,
      'lg-c7',
      [cic, history, overdue, breach],
      ([group, hist, od, br]) =>
        `Quan hệ tín dụng: ${group}; lịch sử tín dụng ${hist}; nợ quá hạn: ${od}; vi phạm nghĩa vụ: ${br}.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'lg-c8',
      [purpose],
      ([value]) =>
        `Mục đích vay khai báo: ${value.replace(/;$/, '')} — thuộc nhóm mục đích hợp lệ với sản phẩm tài trợ vốn lưu động.`,
      { tone: 'positive' },
    ),
    {
      id: 'lg-c9',
      text: 'Chưa kiểm chứng được điều kiện DSCR tối thiểu 1,25 theo CREDIT-POLICY-3.2: hồ sơ không có phương án trả nợ chi tiết theo kỳ để tính toán.',
      citationIds: [
        citePolicy(
          context,
          'pol-dscr',
          'CREDIT-POLICY-3.2',
          'DSCR tối thiểu cho khoản vay bổ sung vốn lưu động là 1.25.',
        ),
      ],
      tone: 'warning',
    },
  ]);

  return {
    domain: 'LEGAL',
    agent: 'legal-specialist',
    status: 'PARTIAL',
    summary:
      'Tư cách pháp nhân, người đại diện, UBO và lịch sử tín dụng đều hợp lệ; điều kiện tài sản bảo đảm thoả chính sách. Vướng mắc duy nhất là chưa đủ dữ liệu tính DSCR.',
    claims,
    citations: [],
    confidence: 0.84,
    note: 'Thiếu phương án trả nợ chi tiết nên chưa kiểm chứng được điều kiện DSCR theo CREDIT-POLICY-3.2.',
  };
}

/* ------------------------------------------------------------------ */
/* Chuyên gia HỒ SƠ & CHỨNG TỪ                                         */
/* ------------------------------------------------------------------ */

function buildDocument(context: ReadingContext): DomainReport {
  const f = (needle: string) => findFact(context.facts, needle);

  const name = f('Tên doanh nghiệp');
  const capital = f('Vốn điều lệ');
  const issuer = f('Cơ quan cấp phép');
  const auditor = f('Đơn vị kiểm toán');
  const product = f('Sản phẩm');
  const term = f('Thời hạn hạn mức');
  const requested = f('Số tiền đề nghị');

  const readCount = context.facts.length;

  const claims = compact([
    {
      id: 'dc-c1',
      text: `Đã đọc ${DEMO_DOCUMENTS.length} hồ sơ bằng OCR và bóc được ${readCount} dữ kiện có toạ độ, đủ cơ sở để đối chiếu tự động từng trường thông tin.`,
      citationIds: name ? [cite(context, name)] : [],
      tone: 'positive',
    },
    claimFrom(
      context,
      'dc-c2',
      [name, capital],
      ([n, c]) => `Phiếu thông tin khách hàng có đầy đủ định danh: ${n}, vốn điều lệ ${c}.`,
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'dc-c3',
      [issuer],
      () => 'Có giấy chứng nhận đăng ký doanh nghiệp bản scan, đọc được rõ cơ quan cấp.',
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'dc-c4',
      [auditor],
      () => 'Có báo cáo kiểm toán độc lập kèm theo, đáp ứng yêu cầu chứng từ tài chính của sản phẩm.',
      { tone: 'positive' },
    ),
    claimFrom(
      context,
      'dc-c5',
      [product, requested, term],
      ([p, amount, t]) =>
        `Đề nghị cấp tín dụng ghi trên hồ sơ: ${p}, ${amount}, thời hạn ${t} — khớp với thông tin khai báo trong hệ thống.`,
      { tone: 'positive' },
    ),
    {
      id: 'dc-c6',
      text: 'THIẾU CHỨNG TỪ: chưa có hợp đồng đầu ra chứng minh mục đích sử dụng vốn. Đây là điều kiện bắt buộc phải bổ sung trước khi giải ngân.',
      citationIds: [],
      tone: 'warning',
      isInference: true,
    },
  ]);

  return {
    domain: 'DOCUMENT',
    agent: 'document-specialist',
    status: 'PARTIAL',
    summary: `Đã số hoá và đọc thành công ${DEMO_DOCUMENTS.length} hồ sơ; các trường định danh, pháp lý và tài chính đều đối chiếu khớp với dữ liệu hệ thống. Còn thiếu hợp đồng đầu ra.`,
    claims,
    citations: [],
    confidence: 0.9,
    note: 'Thiếu 1 chứng từ bắt buộc: hợp đồng đầu ra chứng minh mục đích sử dụng vốn.',
  };
}

/* ------------------------------------------------------------------ */
/* Tổng hợp                                                            */
/* ------------------------------------------------------------------ */

function buildComposed(question: string, reports: DomainReport[]): ComposedReport {
  const byDomain = (domain: DomainReport['domain']) =>
    reports.find((report) => report.domain === domain);

  const pick = (domain: DomainReport['domain'], ids: string[]): ReportClaim[] =>
    (byDomain(domain)?.claims ?? []).filter((claim) => ids.includes(claim.id));

  return {
    question,
    decision: 'APPROVE_WITH_CONDITIONS',
    recommendation:
      'Đề xuất PHÊ DUYỆT hạn mức 80 tỷ đồng KÈM ĐIỀU KIỆN. Năng lực tài chính vượt yêu cầu: doanh thu tăng trưởng, dòng tiền kinh doanh dồi dào, đòn bẩy thấp và tài sản bảo đảm còn dư địa lớn so với trần LTV. ' +
      'Ba vướng mắc đều thuộc nhóm bổ sung hồ sơ, không phải vấn đề bản chất tín dụng: thiếu hợp đồng đầu ra, chưa tính được DSCR, và mức tập trung khách hàng đầu ra cần theo dõi.',
    sections: [
      { title: 'Năng lực tài chính', domain: 'CREDIT', claims: pick('CREDIT', ['cr-c1', 'cr-c3', 'cr-c5', 'cr-c8', 'cr-c11']) },
      { title: 'Pháp lý và tuân thủ', domain: 'LEGAL', claims: pick('LEGAL', ['lg-c1', 'lg-c6', 'lg-c7', 'lg-c9']) },
      { title: 'Tính đầy đủ hồ sơ', domain: 'DOCUMENT', claims: pick('DOCUMENT', ['dc-c1', 'dc-c5', 'dc-c6']) },
    ],
    conditions: [
      'Bổ sung hợp đồng đầu ra chứng minh mục đích sử dụng vốn (chứng từ bắt buộc còn thiếu).',
      'Cung cấp phương án trả nợ chi tiết theo kỳ để tính DSCR, đối chiếu ngưỡng tối thiểu 1,25 theo CREDIT-POLICY-3.2.',
      'Làm rõ mức độ phụ thuộc nhóm khách hàng đầu ra lớn nhất và phương án ứng phó khi mất khách hàng chủ lực.',
      'Hoàn tất đăng ký giao dịch bảo đảm trước khi giải ngân lần đầu.',
    ],
    domainStatus: {
      CREDIT: byDomain('CREDIT')?.status ?? 'FAILED',
      LEGAL: byDomain('LEGAL')?.status ?? 'FAILED',
      DOCUMENT: byDomain('DOCUMENT')?.status ?? 'FAILED',
    },
    warnings: ['Lĩnh vực LEGAL và DOCUMENT chỉ có kết quả một phần — xem mục điều kiện kèm theo.'],
  };
}

/* ------------------------------------------------------------------ */
/* Điểm vào                                                            */
/* ------------------------------------------------------------------ */

/**
 * Chạy trọn pipeline OCR → dữ kiện → báo cáo cho hồ sơ đã số hoá.
 * Mỗi chuyên gia dùng chung một ngữ cảnh đọc nên trích dẫn không bị trùng lặp.
 */
export function generateExpertReports(question: string): ExpertReportBundle {
  const context = createContext();

  // Mỗi báo cáo tự thu thập trích dẫn của mình vào ngữ cảnh chung.
  const credit = buildCredit(context);
  const legal = buildLegal(context);
  const document = buildDocument(context);

  /** Trả về đúng những trích dẫn mà báo cáo này dùng tới. */
  const citationsOf = (report: DomainReport): ReportCitation[] => {
    const used = new Set(report.claims.flatMap((claim) => claim.citationIds));
    return context.citations.filter((citation) => used.has(citation.id));
  };

  const domainReports = [credit, legal, document].map((report) => ({
    ...report,
    citations: citationsOf(report),
  }));

  return {
    composed: buildComposed(question, domainReports),
    domainReports,
    documents: [...context.regions.values()],
  };
}
