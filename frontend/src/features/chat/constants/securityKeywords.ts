/**
 * Từ khoá nhạy cảm cho Banking Safety UX.
 *
 * Danh sách được so khớp trên chuỗi đã bỏ dấu tiếng Việt (xem
 * `src/utils/detectSensitiveContent.ts`), nên chỉ cần viết dạng không dấu.
 *
 * Mục đích: CẢNH BÁO người dùng, không phải chặn nội dung. SH-AI không bao giờ
 * yêu cầu các thông tin này.
 */

/** Thông tin xác thực — tuyệt đối không được chia sẻ trong hội thoại. */
export const CREDENTIAL_KEYWORDS: readonly string[] = [
  'mat khau',
  'matkhau',
  'password',
  'pass word',
  'ma pin',
  'so pin',
  'smart otp',
  'smartotp',
  'ma otp',
  'otp',
  'cvv',
  'cvc',
  'so the tin dung',
  'so the day du',
  'full so the',
  'ma xac thuc',
  'ma bi mat',
  'khoa bao mat',
  'private key',
  'secret key',
  'access token',
  'thong tin dang nhap',
  'tai khoan dang nhap',
  'ten dang nhap va mat khau',
  'ma kich hoat',
];

/** Ý định thực hiện giao dịch — demo không thực hiện giao dịch thật. */
export const TRANSACTION_KEYWORDS: readonly string[] = [
  'chuyen tien',
  'chuyen khoan',
  'thuc hien giao dich',
  'rut tien',
  'thanh toan hoa don',
  'nap tien',
  'mo the ngay',
  'giai ngan',
  'dong bang tai khoan',
  'khoa the',
];

/** Chủ đề tư vấn tài chính — cần disclaimer tham khảo. */
export const FINANCIAL_ADVICE_KEYWORDS: readonly string[] = [
  'lai suat',
  'vay',
  'khoan vay',
  'tra gop',
  'tiet kiem',
  'tien gui',
  'dau tu',
  'ty gia',
  'han muc',
  'tham dinh',
  'the tin dung',
  'bao lanh',
];

/** Thông điệp cảnh báo chuẩn — dùng thống nhất toàn ứng dụng. */
export const SECURITY_MESSAGES = {
  credential:
    'Vì sự an toàn của bạn, không chia sẻ mật khẩu, mã PIN, OTP, CVV hoặc thông tin xác thực trong cuộc trò chuyện.',
  transaction: 'SH-AI không trực tiếp thực hiện giao dịch trong phiên bản demo này.',
  financialAdvice:
    'Thông tin do SH-AI cung cấp mang tính tham khảo và không thay thế kết quả thẩm định hoặc tư vấn chính thức từ SHB.',
  composerDisclaimer:
    'SH-AI có thể đưa ra thông tin chưa chính xác. Không cung cấp mật khẩu, mã PIN, OTP hoặc thông tin bảo mật trong cuộc trò chuyện.',
} as const;
