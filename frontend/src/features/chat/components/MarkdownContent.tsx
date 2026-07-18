import { Fragment, memo, useMemo, type ReactNode } from 'react';
import { parseMarkdown, type InlineToken, type MarkdownNode } from '@/features/chat/utils/parseMarkdown';
import styles from './MarkdownContent.module.css';

export interface MarkdownContentProps {
  content: string;
  className?: string;
}

function renderInline(tokens: InlineToken[]): ReactNode {
  return tokens.map((token, index) => {
    const key = `${token.type}-${index}`;

    switch (token.type) {
      case 'bold':
        return (
          <strong key={key} className={styles.strong}>
            {token.value}
          </strong>
        );
      case 'italic':
        return <em key={key}>{token.value}</em>;
      case 'code':
        return (
          <code key={key} className={styles.inlineCode}>
            {token.value}
          </code>
        );
      case 'link':
        return (
          // rel="noopener noreferrer": chặn tab-nabbing khi mở tab mới.
          <a
            key={key}
            className={styles.link}
            href={token.href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {token.value}
          </a>
        );
      case 'text':
      default:
        return <Fragment key={key}>{token.value}</Fragment>;
    }
  });
}

const HEADING_CLASS: Record<2 | 3 | 4, string> = {
  2: styles.h2,
  3: styles.h3,
  4: styles.h4,
};

function renderNode(node: MarkdownNode, index: number): ReactNode {
  const key = `${node.type}-${index}`;

  switch (node.type) {
    case 'heading': {
      // Câu trả lời AI nằm dưới h1 của trang -> bắt đầu từ h2 để giữ đúng thứ bậc.
      const Tag = `h${node.level}` as 'h2' | 'h3' | 'h4';
      return (
        <Tag key={key} className={[styles.heading, HEADING_CLASS[node.level]].join(' ')}>
          {renderInline(node.tokens)}
        </Tag>
      );
    }

    case 'paragraph':
      return (
        <p key={key} className={styles.paragraph}>
          {renderInline(node.tokens)}
        </p>
      );

    case 'bulletList':
      return (
        <ul key={key} className={styles.list}>
          {node.items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInline(item)}</li>
          ))}
        </ul>
      );

    case 'numberedList':
      return (
        <ol key={key} className={styles.list}>
          {node.items.map((item, itemIndex) => (
            <li key={itemIndex}>{renderInline(item)}</li>
          ))}
        </ol>
      );

    case 'quote':
      return (
        <blockquote key={key} className={styles.quote}>
          {renderInline(node.tokens)}
        </blockquote>
      );

    case 'code':
      return (
        <pre key={key} className={styles.codeBlock}>
          <code>{node.value}</code>
        </pre>
      );

    case 'table':
      return (
        <div key={key} className={styles.tableScroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                {node.headers.map((header, headerIndex) => (
                  <th
                    key={headerIndex}
                    className={alignClass(node.aligns[headerIndex])}
                    scope="col"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {node.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className={alignClass(node.aligns[cellIndex])}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );

    default:
      return null;
  }
}

function alignClass(align?: 'left' | 'right' | 'center'): string | undefined {
  if (align === 'right') return styles.alignRight;
  if (align === 'center') return styles.alignCenter;
  return undefined;
}

/**
 * Render markdown an toàn.
 *
 * Không dùng `dangerouslySetInnerHTML` ở bất kỳ đâu: mọi node được dựng thành
 * React element, link chỉ chấp nhận http/https (xem `parseMarkdown.ts`).
 */
export const MarkdownContent = memo(function MarkdownContent({
  content,
  className,
}: MarkdownContentProps) {
  const nodes = useMemo(() => parseMarkdown(content), [content]);

  return (
    <div className={[styles.content, className].filter(Boolean).join(' ')}>
      {nodes.map(renderNode)}
    </div>
  );
});
