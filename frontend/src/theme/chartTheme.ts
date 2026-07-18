import { shbColors, shbTypography } from './tokens';

/**
 * Palette cho Ant Design Charts.
 *
 * Nguyên tắc:
 * - Xen kẽ cam ↔ indigo để hai chuỗi cạnh nhau luôn khác biệt cả về tông màu
 *   lẫn độ sáng (phân biệt được khi in đen trắng và với người mù màu).
 * - Không rainbow, không neon.
 * - Không dùng đỏ cho dữ liệu bình thường (đỏ chỉ dành cho trạng thái lỗi).
 */
export const shbChartPalette = [
  shbColors.orange[500], // #F37021
  shbColors.navy[700], // #2F2E79
  shbColors.orange[300],
  shbColors.navy[400],
  shbColors.orange[200],
  shbColors.navy[200],
];

/**
 * Theme dùng chung cho mọi chart, truyền vào Ant Design Charts qua `BaseChart`.
 * Không chứa dữ liệu domain.
 */
export const shbChartTheme = {
  type: 'light' as const,
  category10: shbChartPalette,
  category20: [...shbChartPalette, ...shbChartPalette],
  view: {
    viewFill: 'transparent',
  },
  token: {
    colorBackground: 'transparent',
    colorStroke: shbColors.neutral.border,
  },
  axis: {
    labelFontFamily: shbTypography.fontFamily,
    labelFontSize: 12,
    labelFill: shbColors.neutral.textSecondary,
    lineStroke: shbColors.neutral.border,
    tickStroke: shbColors.neutral.border,
    gridStroke: shbColors.neutral.border,
    gridStrokeOpacity: 0.6,
    gridLineDash: [3, 4],
  },
  legend: {
    itemLabelFontFamily: shbTypography.fontFamily,
    itemLabelFontSize: 12,
    itemLabelFill: shbColors.neutral.textSecondary,
  },
  label: {
    fontFamily: shbTypography.fontFamily,
    fontSize: 12,
    fill: shbColors.neutral.textPrimary,
  },
  tooltip: {
    fontFamily: shbTypography.fontFamily,
  },
};
