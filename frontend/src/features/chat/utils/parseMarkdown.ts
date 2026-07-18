/**
 * Parser Markdown giới hạn cho câu trả lời của AI.
 *
 * BẢO MẬT: parser này chỉ tạo ra cấu trúc dữ liệu; phần render dựng React
 * element trực tiếp từ cấu trúc đó (xem `MarkdownContent.tsx`). Không có bước
 * nào sinh HTML chuỗi, nên không tồn tại đường cho script injection.
 *
 * Cú pháp hỗ trợ: heading, đoạn văn, bullet list, numbered list, blockquote,
 * code block, bảng, và inline (bold, italic, code, link).
 */

export type InlineToken =
  | { type: 'text'; value: string }
  | { type: 'bold'; value: string }
  | { type: 'italic'; value: string }
  | { type: 'code'; value: string }
  | { type: 'link'; value: string; href: string };

export type MarkdownNode =
  | { type: 'heading'; level: 2 | 3 | 4; tokens: InlineToken[] }
  | { type: 'paragraph'; tokens: InlineToken[] }
  | { type: 'bulletList'; items: InlineToken[][] }
  | { type: 'numberedList'; items: InlineToken[][] }
  | { type: 'quote'; tokens: InlineToken[] }
  | { type: 'code'; value: string; lang?: string }
  | { type: 'table'; headers: string[]; rows: string[][]; aligns: Array<'left' | 'right' | 'center'> };

/**
 * Chỉ cho phép link http/https.
 * Chặn `javascript:`, `data:`, `vbscript:`… ngay từ khâu parse.
 */
function sanitizeHref(raw: string): string | null {
  const href = raw.trim();
  try {
    // Cho phép đường dẫn nội bộ dạng /path.
    if (href.startsWith('/')) return href;

    const url = new URL(href);
    if (url.protocol === 'http:' || url.protocol === 'https:') return url.toString();
    return null;
  } catch {
    return null;
  }
}

const INLINE_PATTERN = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\n]+\*)|(\[[^\]]+\]\([^)\s]+\))/g;

/** Tách một dòng thành các token inline. */
export function parseInline(input: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let lastIndex = 0;

  for (const match of input.matchAll(INLINE_PATTERN)) {
    const index = match.index ?? 0;

    if (index > lastIndex) {
      tokens.push({ type: 'text', value: input.slice(lastIndex, index) });
    }

    const [raw] = match;

    if (raw.startsWith('`')) {
      tokens.push({ type: 'code', value: raw.slice(1, -1) });
    } else if (raw.startsWith('**')) {
      tokens.push({ type: 'bold', value: raw.slice(2, -2) });
    } else if (raw.startsWith('*')) {
      tokens.push({ type: 'italic', value: raw.slice(1, -1) });
    } else if (raw.startsWith('[')) {
      const linkMatch = raw.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
      if (linkMatch) {
        const href = sanitizeHref(linkMatch[2]);
        if (href) {
          tokens.push({ type: 'link', value: linkMatch[1], href });
        } else {
          // Link không an toàn -> hiển thị dưới dạng text thuần.
          tokens.push({ type: 'text', value: linkMatch[1] });
        }
      } else {
        tokens.push({ type: 'text', value: raw });
      }
    }

    lastIndex = index + raw.length;
  }

  if (lastIndex < input.length) {
    tokens.push({ type: 'text', value: input.slice(lastIndex) });
  }

  return tokens;
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

function parseAligns(separator: string): Array<'left' | 'right' | 'center'> {
  return parseTableRow(separator).map((cell) => {
    const startsColon = cell.startsWith(':');
    const endsColon = cell.endsWith(':');
    if (startsColon && endsColon) return 'center';
    if (endsColon) return 'right';
    return 'left';
  });
}

const isTableSeparator = (line: string) => /^\s*\|?[\s:-]*-[\s:|-]*\|?\s*$/.test(line) && line.includes('-');

/** Chuyển markdown thành danh sách node để render. */
export function parseMarkdown(input: string): MarkdownNode[] {
  const lines = input.replace(/\r\n/g, '\n').split('\n');
  const nodes: MarkdownNode[] = [];

  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    // Dòng trống
    if (!line.trim()) {
      index += 1;
      continue;
    }

    // Code block
    if (line.trimStart().startsWith('```')) {
      const lang = line.trim().slice(3).trim() || undefined;
      const buffer: string[] = [];
      index += 1;

      while (index < lines.length && !lines[index].trimStart().startsWith('```')) {
        buffer.push(lines[index]);
        index += 1;
      }
      index += 1; // bỏ qua ``` đóng

      nodes.push({ type: 'code', value: buffer.join('\n'), ...(lang ? { lang } : {}) });
      continue;
    }

    // Heading
    const headingMatch = line.match(/^(#{2,4})\s+(.*)$/);
    if (headingMatch) {
      const level = headingMatch[1].length as 2 | 3 | 4;
      nodes.push({ type: 'heading', level, tokens: parseInline(headingMatch[2]) });
      index += 1;
      continue;
    }

    // Table: cần dòng header + dòng phân cách
    if (line.includes('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const headers = parseTableRow(line);
      const aligns = parseAligns(lines[index + 1]);
      index += 2;

      const rows: string[][] = [];
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(parseTableRow(lines[index]));
        index += 1;
      }

      nodes.push({ type: 'table', headers, rows, aligns });
      continue;
    }

    // Blockquote
    if (line.trimStart().startsWith('>')) {
      const buffer: string[] = [];
      while (index < lines.length && lines[index].trimStart().startsWith('>')) {
        buffer.push(lines[index].trimStart().replace(/^>\s?/, ''));
        index += 1;
      }
      nodes.push({ type: 'quote', tokens: parseInline(buffer.join(' ')) });
      continue;
    }

    // Bullet list
    if (/^\s*[-*]\s+/.test(line)) {
      const items: InlineToken[][] = [];
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(parseInline(lines[index].replace(/^\s*[-*]\s+/, '')));
        index += 1;
      }
      nodes.push({ type: 'bulletList', items });
      continue;
    }

    // Numbered list
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: InlineToken[][] = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(parseInline(lines[index].replace(/^\s*\d+\.\s+/, '')));
        index += 1;
      }
      nodes.push({ type: 'numberedList', items });
      continue;
    }

    // Đoạn văn: gom các dòng liền nhau cho tới dòng trống hoặc block mới.
    const buffer: string[] = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^\s*[-*]\s+/.test(lines[index]) &&
      !/^\s*\d+\.\s+/.test(lines[index]) &&
      !lines[index].trimStart().startsWith('>') &&
      !lines[index].trimStart().startsWith('```') &&
      !/^#{2,4}\s+/.test(lines[index])
    ) {
      buffer.push(lines[index].trim());
      index += 1;
    }

    if (buffer.length) {
      nodes.push({ type: 'paragraph', tokens: parseInline(buffer.join(' ')) });
    }
  }

  return nodes;
}
