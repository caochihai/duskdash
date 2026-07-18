import {
  CREDENTIAL_KEYWORDS,
  FINANCIAL_ADVICE_KEYWORDS,
  SECURITY_MESSAGES,
  TRANSACTION_KEYWORDS,
} from '@/features/chat/constants/securityKeywords';

export type SensitiveKind = 'credential' | 'transaction' | 'financialAdvice';

export interface SensitiveDetection {
  kind: SensitiveKind;
  message: string;
}

/**
 * Bỏ dấu tiếng Việt + chuẩn hoá khoảng trắng để so khớp từ khoá không phụ thuộc
 * cách gõ dấu ("mật khẩu" / "mat khau" / "MẬT KHẨU" đều khớp).
 */
export function normalizeVietnamese(input: string): string {
  return input
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // bỏ dấu thanh & dấu phụ (sau NFD)
    .replace(/đ/g, 'd') // đ -> d (không bị NFD tách)
    .replace(/[^a-z0-9\s]/g, ' ') // bỏ ký tự đặc biệt
    .replace(/\s+/g, ' ')
    .trim();
}

function containsKeyword(normalized: string, keywords: readonly string[]): boolean {
  // Đệm khoảng trắng hai đầu để so khớp theo ranh giới từ,
  // tránh "otp" khớp nhầm trong "laptop".
  const padded = ` ${normalized} `;
  return keywords.some((keyword) => padded.includes(` ${keyword} `));
}

/**
 * Phát hiện nội dung nhạy cảm trong tin nhắn người dùng.
 *
 * Lưu ý bảo mật: hàm này KHÔNG log nội dung đầu vào ở bất kỳ trường hợp nào.
 * Chỉ trả về loại cảnh báo cần hiển thị.
 */
export function detectSensitiveContent(input: string): SensitiveDetection | null {
  if (!input.trim()) return null;

  const normalized = normalizeVietnamese(input);

  // Ưu tiên cao nhất: thông tin xác thực.
  if (containsKeyword(normalized, CREDENTIAL_KEYWORDS)) {
    return { kind: 'credential', message: SECURITY_MESSAGES.credential };
  }

  if (containsKeyword(normalized, TRANSACTION_KEYWORDS)) {
    return { kind: 'transaction', message: SECURITY_MESSAGES.transaction };
  }

  if (containsKeyword(normalized, FINANCIAL_ADVICE_KEYWORDS)) {
    return { kind: 'financialAdvice', message: SECURITY_MESSAGES.financialAdvice };
  }

  return null;
}

/** Chuỗi số dài (≥12 chữ số) trông giống số thẻ — cảnh báo sớm. */
export function looksLikeCardNumber(input: string): boolean {
  const digitsOnly = input.replace(/[\s-]/g, '');
  return /\d{12,19}/.test(digitsOnly);
}
