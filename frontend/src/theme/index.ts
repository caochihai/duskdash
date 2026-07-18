import type { ThemeConfig } from 'antd';
import { shbColors, shbRadius, shbTypography } from './tokens';
import { shbComponentOverrides } from './componentOverrides';

/**
 * Theme SHB tập trung cho Ant Design ConfigProvider.
 * Được nạp một lần duy nhất tại `src/app/AppProviders.tsx`.
 */
export const shbTheme: ThemeConfig = {
  token: {
    // Thương hiệu
    colorPrimary: shbColors.orange[500],
    colorPrimaryHover: shbColors.orange[400],
    colorPrimaryActive: shbColors.orange[600],
    colorPrimaryBg: shbColors.orange[50],
    colorPrimaryBgHover: shbColors.orange[100],
    colorPrimaryBorder: shbColors.orange[200],

    colorLink: shbColors.orange[600],
    colorLinkHover: shbColors.orange[500],
    colorLinkActive: shbColors.orange[700],

    // Chữ
    colorText: shbColors.neutral.textPrimary,
    colorTextSecondary: shbColors.neutral.textSecondary,
    colorTextTertiary: shbColors.neutral.textMuted,
    colorTextHeading: shbColors.navy[700],
    colorTextDescription: shbColors.neutral.textSecondary,

    // Nền
    colorBgLayout: shbColors.neutral.canvas,
    colorBgContainer: shbColors.neutral.surface,
    colorBgElevated: shbColors.neutral.white,
    colorBgSpotlight: shbColors.navy[800],

    // Viền
    colorBorder: shbColors.neutral.border,
    colorBorderSecondary: shbColors.neutral.border,

    // Ngữ nghĩa
    colorSuccess: shbColors.semantic.success,
    colorWarning: shbColors.semantic.warning,
    colorError: shbColors.semantic.error,
    colorInfo: shbColors.semantic.info,

    // Hình dạng
    borderRadius: shbRadius.medium,
    borderRadiusLG: shbRadius.large,
    borderRadiusSM: shbRadius.small,
    borderRadiusXS: 6,

    // Typography
    fontFamily: shbTypography.fontFamily,
    fontFamilyCode: shbTypography.fontFamilyCode,
    fontSize: shbTypography.size.body,
    fontSizeLG: shbTypography.size.bodyLarge,
    fontSizeSM: shbTypography.size.supporting,
    fontSizeHeading1: 34,
    fontSizeHeading2: 26,
    fontSizeHeading3: 20,
    fontSizeHeading4: 17,
    lineHeight: shbTypography.lineHeight.body,

    // Control
    controlHeight: 40,
    controlHeightLG: 46,
    controlHeightSM: 32,

    // Motion — micro-interaction do CSS/Motion đảm nhiệm, giữ AntD nhanh & nhẹ.
    motionDurationFast: '0.12s',
    motionDurationMid: '0.18s',
    motionDurationSlow: '0.24s',

    // Focus ring rõ ràng (accessibility)
    lineWidthFocus: 3,
    controlOutline: 'rgba(243, 112, 33, 0.16)',
    controlOutlineWidth: 3,

    wireframe: false,
  },

  components: shbComponentOverrides,
};

export { shbColors, shbRadius, shbShadow, shbTypography, shbLayout, shbMotion } from './tokens';
export { shbChartTheme, shbChartPalette } from './chartTheme';
