/**
 * SHB Design Tokens
 * ------------------------------------------------------------------
 * Nguồn màu thương hiệu: trích xuất trực tiếp từ logo SVG chính thức
 * (`public/brand/shb-logo.svg`, tải từ https://new.shb.com.vn/vi).
 *
 *   Orange  #F37021  — màu nhấn / CTA
 *   Indigo  #2F2E79  — màu heading / thương hiệu
 *
 * Đây là hai giá trị chuẩn, KHÔNG phải giá trị phỏng đoán. Các bậc còn lại
 * của thang màu được dựng quanh hai giá trị này.
 *
 * Toàn bộ component phải đọc màu từ đây (qua theme token hoặc CSS variable),
 * không hard-code mã màu trực tiếp.
 */

export const shbColors = {
  /** Cam SHB — màu nhấn, CTA. Bậc 500 là màu thương hiệu chính thức. */
  orange: {
    50: '#FFF7F0',
    100: '#FEEBDD',
    200: '#FDD3B5',
    300: '#FCB37F',
    400: '#F88C46',
    500: '#F37021', // Official SHB orange
    600: '#DD5A12',
    700: '#B9450C',
    800: '#93370D',
    900: '#762F0F',
  },

  /** Indigo SHB — heading, text thương hiệu. Bậc 700 là màu chính thức. */
  navy: {
    50: '#F3F3FA',
    100: '#E1E1F3',
    200: '#C0BFE7',
    300: '#9795D6',
    400: '#6F6DC4',
    500: '#4F4DB0',
    600: '#3C3A96',
    700: '#2F2E79', // Official SHB indigo
    800: '#23224F',
    900: '#1B1A46',
  },

  /** Trung tính ấm — nền, viền, chữ. */
  neutral: {
    white: '#FFFFFF',
    warmWhite: '#FFFDF9',
    canvas: '#F7F5F1',
    surface: '#FFFFFF',
    surfaceSoft: '#FFF9F4',
    border: '#EAE3DA',
    borderStrong: '#D9D0C5',
    textPrimary: '#18212B',
    textSecondary: '#667085',
    textMuted: '#98A2B3',
  },

  /** Ngữ nghĩa — trạng thái. */
  semantic: {
    success: '#15805D',
    successBg: '#ECFAF4',
    warning: '#D97706',
    warningBg: '#FFF8EB',
    error: '#C9362B',
    errorBg: '#FEF3F2',
    info: '#276A92',
    infoBg: '#EFF8FC',
  },
} as const;

/** Bo góc. */
export const shbRadius = {
  small: 8,
  medium: 12,
  large: 18,
  card: 20,
  composer: 26,
  pill: 999,
} as const;

/** Shadow nhẹ, tự nhiên — không dùng shadow đen mạnh. */
export const shbShadow = {
  small: '0 2px 8px rgba(35, 34, 79, 0.06)',
  medium: '0 8px 30px rgba(35, 34, 79, 0.08)',
  large: '0 16px 48px rgba(35, 34, 79, 0.12)',
  orangeGlow: '0 0 0 4px rgba(243, 112, 33, 0.10)',
} as const;

/** Typography. */
export const shbTypography = {
  fontFamily:
    'Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif',
  fontFamilyCode:
    'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
  size: {
    caption: 12,
    small: 13,
    supporting: 14,
    body: 15,
    bodyLarge: 16,
    sectionHeading: 22,
    heroMobile: 30,
    heroDesktop: 40,
  },
  lineHeight: {
    heading: 1.22,
    body: 1.7,
    caption: 1.45,
  },
} as const;

/** Kích thước layout. */
export const shbLayout = {
  sidebarWidth: 288,
  sidebarCollapsedWidth: 76,
  headerHeight: 64,
  /** Độ rộng đọc tối ưu cho nội dung AI. */
  contentMaxWidth: 820,
  /** Độ rộng vùng chat / composer. */
  chatMaxWidth: 880,
  mobileBreakpoint: 768,
  tabletBreakpoint: 1200,
} as const;

/** Thời lượng chuyển động (ms). */
export const shbMotion = {
  micro: 0.18,
  message: 0.22,
  panel: 0.28,
  page: 0.24,
  /** easing chuẩn — mềm, không nảy. */
  ease: [0.22, 1, 0.36, 1] as const,
} as const;

export type ShbColors = typeof shbColors;
