import { useMemo } from 'react';
import { Collapse, Popover, Tag, Tooltip } from 'antd';
import {
  AimOutlined,
  CheckCircleFilled,
  ExclamationCircleFilled,
  MinusCircleFilled,
} from '@ant-design/icons';
import {
  CITATION_SOURCE_LABEL,
  DECISION_LABEL,
  REPORT_DOMAIN_LABEL,
  REPORT_STATUS_LABEL,
  type ComposedReport,
  type ExpertReportBundle,
  type ReportCitation,
  type ReportClaim,
  type ReportStatus,
} from '@/types/report';
import type { SourceLocator } from '@/types/source';
import styles from './ExpertReport.module.css';

interface ExpertReportProps {
  bundle: ExpertReportBundle;
  /** Mở hồ sơ gốc và khoanh đỏ đúng vùng của trích dẫn. */
  onOpenLocator?: (locator: SourceLocator) => void;
}

const STATUS_COLOR: Record<ReportStatus, string> = {
  OK: 'green',
  PARTIAL: 'gold',
  FAILED: 'red',
};

const DECISION_COLOR: Record<ComposedReport['decision'], string> = {
  APPROVE: 'green',
  APPROVE_WITH_CONDITIONS: 'gold',
  DECLINE: 'red',
  NEED_MORE_INFO: 'blue',
};

function ClaimMark({ tone }: { tone?: ReportClaim['tone'] }) {
  if (tone === 'positive') {
    return (
      <CheckCircleFilled className={[styles.claimMark, styles.markPositive].join(' ')} aria-label="Thuận lợi" />
    );
  }
  if (tone === 'warning') {
    return (
      <ExclamationCircleFilled
        className={[styles.claimMark, styles.markWarning].join(' ')}
        aria-label="Cần lưu ý"
      />
    );
  }
  return (
    <MinusCircleFilled className={[styles.claimMark, styles.markNeutral].join(' ')} aria-label="Trung tính" />
  );
}

/**
 * Chip số trích dẫn đặt ngay sau luận điểm.
 *
 * Trích dẫn kiểu DOCUMENT bấm là mở hồ sơ gốc và khoanh đỏ đúng dòng; các loại
 * còn lại hiện popover với nguyên văn đoạn được trích và định danh nguồn.
 */
function CitationChip({
  index,
  citation,
  onOpenLocator,
}: {
  index: number;
  citation: ReportCitation;
  onOpenLocator?: (locator: SourceLocator) => void;
}) {
  const meta =
    citation.policyClauseId ??
    citation.recordRef ??
    citation.sqlRef ??
    citation.locator?.documentTitle ??
    '';

  const isDocument = citation.sourceType === 'DOCUMENT' && Boolean(citation.locator);

  const content = (
    <div className={styles.popQuote}>
      <Tag color="orange" style={{ marginBottom: 6 }}>
        {CITATION_SOURCE_LABEL[citation.sourceType]}
      </Tag>
      <div>“{citation.quote}”</div>
      {meta && <span className={styles.popMeta}>{meta}</span>}
      {isDocument && (
        <span className={styles.popMeta}>
          <AimOutlined /> Bấm để mở hồ sơ và khoanh vùng trích dẫn
        </span>
      )}
    </div>
  );

  return (
    <Popover content={content} trigger={['hover', 'focus']} placement="top">
      <button
        type="button"
        className={[styles.cite, isDocument ? styles.citeDocument : ''].filter(Boolean).join(' ')}
        onClick={() => {
          if (isDocument && citation.locator && onOpenLocator) onOpenLocator(citation.locator);
        }}
        aria-label={`Nguồn ${index}: ${CITATION_SOURCE_LABEL[citation.sourceType]} — ${citation.quote}`}
      >
        {index}
      </button>
    </Popover>
  );
}

function ClaimItem({
  claim,
  citationIndex,
  onOpenLocator,
}: {
  claim: ReportClaim;
  citationIndex: Map<string, { index: number; citation: ReportCitation }>;
  onOpenLocator?: (locator: SourceLocator) => void;
}) {
  const resolved = claim.citationIds
    .map((id) => citationIndex.get(id))
    .filter((item): item is { index: number; citation: ReportCitation } => item !== undefined);

  return (
    <li className={styles.claim}>
      <ClaimMark tone={claim.tone} />
      <span>
        {claim.isInference && (
          <Tooltip title="Suy luận từ nhiều nguồn, không đọc thẳng từ một chứng từ">
            <span className={styles.inferenceTag}>suy luận</span>
          </Tooltip>
        )}
        {claim.text}
        {resolved.length > 0 ? (
          <span className={styles.citeGroup}>
            {resolved.map(({ index, citation }) => (
              <CitationChip
                key={citation.id}
                index={index}
                citation={citation}
                {...(onOpenLocator ? { onOpenLocator } : {})}
              />
            ))}
          </span>
        ) : (
          // Không nguồn mà cũng không phải suy luận -> vi phạm bất biến, phải lộ ra.
          !claim.isInference && <span className={styles.noSource}>⚠ chưa có nguồn</span>
        )}
      </span>
    </li>
  );
}

/**
 * Báo cáo của hệ chuyên gia số trình chuyên viên tín dụng.
 *
 * Bố cục theo đúng thứ tự người ra quyết định cần: kết luận và điều kiện trước,
 * rồi mới tới báo cáo chi tiết từng lĩnh vực. Mỗi luận điểm mang số trích dẫn
 * bấm được — nói tới đâu, dẫn nguồn tới đó.
 */
export function ExpertReport({ bundle, onOpenLocator }: ExpertReportProps) {
  const { composed, domainReports } = bundle;

  // Đánh số trích dẫn liên tục toàn báo cáo để chuyên viên đối chiếu nhanh.
  const citationIndex = useMemo(() => {
    const map = new Map<string, { index: number; citation: ReportCitation }>();
    let counter = 1;
    for (const report of domainReports) {
      for (const citation of report.citations) {
        if (!map.has(citation.id)) {
          map.set(citation.id, { index: counter, citation });
          counter += 1;
        }
      }
    }
    return map;
  }, [domainReports]);

  const totalCitations = citationIndex.size;
  const documentCitations = [...citationIndex.values()].filter(
    (item) => item.citation.sourceType === 'DOCUMENT',
  ).length;

  return (
    <section className={styles.report} aria-label="Báo cáo thẩm định của hệ chuyên gia số">
      {/* 1. Kết luận — thứ chuyên viên cần đọc trước tiên. */}
      <div className={styles.verdict}>
        <div className={styles.verdictHead}>
          <span className={styles.verdictTitle}>Kết luận thẩm định</span>
          <Tag color={DECISION_COLOR[composed.decision]} style={{ marginInlineEnd: 0 }}>
            {DECISION_LABEL[composed.decision]}
          </Tag>
        </div>
        <p className={styles.recommendation}>{composed.recommendation}</p>
      </div>

      {/* 2. Trạng thái từng chuyên gia. */}
      <div className={styles.domainStrip}>
        {domainReports.map((report) => (
          <span key={report.domain} className={styles.domainPill}>
            {REPORT_DOMAIN_LABEL[report.domain]}
            <Tag color={STATUS_COLOR[report.status]} style={{ marginInlineEnd: 0 }}>
              {REPORT_STATUS_LABEL[report.status]}
            </Tag>
            <span style={{ color: '#98A2B3', fontWeight: 500 }}>
              tin cậy {Math.round(report.confidence * 100)}%
            </span>
          </span>
        ))}
      </div>

      {/* 3. Điều kiện phải xử lý — hành động cụ thể cho chuyên viên. */}
      {composed.conditions && composed.conditions.length > 0 && (
        <div className={styles.conditions}>
          <p className={styles.conditionsTitle}>
            Điều kiện phải hoàn tất trước giải ngân ({composed.conditions.length})
          </p>
          <ol className={styles.conditionList}>
            {composed.conditions.map((condition) => (
              <li key={condition}>{condition}</li>
            ))}
          </ol>
        </div>
      )}

      {/* 4. Báo cáo chi tiết của từng chuyên gia. */}
      <div className={styles.body}>
        <Collapse
          ghost
          defaultActiveKey={domainReports.map((report) => report.domain)}
          items={domainReports.map((report) => ({
            key: report.domain,
            label: (
              <span className={styles.sectionTitle}>
                Báo cáo {REPORT_DOMAIN_LABEL[report.domain]}
                <Tag color={STATUS_COLOR[report.status]}>{REPORT_STATUS_LABEL[report.status]}</Tag>
                <span style={{ fontWeight: 400, color: '#98A2B3', fontSize: 12 }}>
                  {report.claims.length} luận điểm · {report.citations.length} nguồn
                </span>
              </span>
            ),
            children: (
              <>
                <p className={styles.summary}>{report.summary}</p>
                <ul className={styles.claimList}>
                  {report.claims.map((claim) => (
                    <ClaimItem
                      key={claim.id}
                      claim={claim}
                      citationIndex={citationIndex}
                      {...(onOpenLocator ? { onOpenLocator } : {})}
                    />
                  ))}
                </ul>
                {report.note && (
                  <p className={styles.summary} style={{ marginTop: 10, borderLeftColor: '#F88C46' }}>
                    Ghi chú: {report.note}
                  </p>
                )}
              </>
            ),
          }))}
        />
      </div>

      <p className={styles.footer}>
        {totalCitations} nguồn được trích dẫn, trong đó {documentCitations} nguồn trỏ trực tiếp
        vào hồ sơ gốc — bấm số trích dẫn để xem đúng vị trí trên chứng từ. Kết quả là đề xuất
        của hệ chuyên gia số; quyết định phê duyệt thuộc thẩm quyền chuyên viên và được ghi vết
        kiểm toán.
      </p>
    </section>
  );
}
