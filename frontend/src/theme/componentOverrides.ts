import type { ThemeConfig } from 'antd';
import { shbColors, shbRadius, shbShadow, shbTypography } from './tokens';

/**
 * Component-level overrides cho Ant Design ConfigProvider.
 *
 * Thứ tự ưu tiên khi tạo style:
 *   1. Ant Design props
 *   2. ConfigProvider token (file này)
 *   3. CSS Modules
 *
 * Mục tiêu: loại bỏ cảm giác "template Ant Design mặc định" mà vẫn giữ
 * khả năng bảo trì của Ant Design.
 */
export const shbComponentOverrides: ThemeConfig['components'] = {
  Button: {
    borderRadius: shbRadius.medium,
    borderRadiusLG: shbRadius.medium + 2,
    borderRadiusSM: shbRadius.small,
    controlHeight: 40,
    controlHeightLG: 46,
    controlHeightSM: 32,
    fontWeight: 500,
    primaryShadow: 'none',
    defaultShadow: 'none',
    dangerShadow: 'none',
    paddingInline: 18,
  },

  Input: {
    borderRadius: shbRadius.medium,
    controlHeight: 40,
    colorBorder: shbColors.neutral.border,
    activeBorderColor: shbColors.orange[500],
    hoverBorderColor: shbColors.orange[300],
    activeShadow: shbShadow.orangeGlow,
    colorTextPlaceholder: shbColors.neutral.textMuted,
    paddingInline: 14,
  },

  Select: {
    borderRadius: shbRadius.medium,
    controlHeight: 40,
    optionSelectedBg: shbColors.orange[50],
    optionSelectedColor: shbColors.navy[700],
    optionSelectedFontWeight: 600,
    colorBorder: shbColors.neutral.border,
  },

  Layout: {
    bodyBg: shbColors.neutral.canvas,
    headerBg: 'transparent',
    siderBg: shbColors.neutral.warmWhite,
    headerHeight: 64,
    headerPadding: '0 20px',
  },

  Menu: {
    itemBorderRadius: shbRadius.medium,
    itemHeight: 40,
    itemSelectedBg: shbColors.orange[50],
    itemSelectedColor: shbColors.navy[700],
    itemActiveBg: shbColors.orange[50],
    itemHoverBg: 'rgba(243, 112, 33, 0.06)',
    itemColor: shbColors.neutral.textSecondary,
    activeBarWidth: 0,
    iconMarginInlineEnd: 10,
    subMenuItemBg: 'transparent',
  },

  Drawer: {
    paddingLG: 20,
    colorBgElevated: shbColors.neutral.warmWhite,
  },

  Dropdown: {
    borderRadiusLG: shbRadius.large,
    controlItemBgHover: shbColors.orange[50],
    controlItemBgActive: shbColors.orange[50],
    boxShadowSecondary: shbShadow.large,
  },

  Card: {
    borderRadiusLG: shbRadius.card,
    colorBorderSecondary: shbColors.neutral.border,
    paddingLG: 20,
    boxShadowTertiary: shbShadow.small,
    headerFontSize: 16,
  },

  Tag: {
    borderRadiusSM: shbRadius.pill,
    defaultBg: shbColors.orange[50],
    defaultColor: shbColors.orange[700],
    fontSizeSM: 12,
    lineHeightSM: 1.6,
  },

  Modal: {
    borderRadiusLG: shbRadius.card,
    paddingContentHorizontalLG: 24,
    titleFontSize: 18,
    titleColor: shbColors.navy[700],
  },

  Upload: {
    colorBorder: shbColors.neutral.border,
    borderRadiusLG: shbRadius.large,
  },

  Tooltip: {
    borderRadius: shbRadius.small,
    colorBgSpotlight: shbColors.navy[800],
    colorTextLightSolid: '#FFFFFF',
    fontSize: 13,
  },

  Skeleton: {
    // Skeleton beige/cam rất nhạt thay vì xám lạnh mặc định.
    color: 'rgba(234, 227, 218, 0.55)',
    colorGradientEnd: 'rgba(255, 247, 240, 0.9)',
    borderRadiusSM: shbRadius.small,
  },

  Notification: {
    borderRadiusLG: shbRadius.large,
    boxShadow: shbShadow.large,
    paddingContentHorizontal: 18,
  },

  Alert: {
    borderRadiusLG: shbRadius.medium,
    colorInfoBg: shbColors.semantic.infoBg,
    colorInfoBorder: '#CBE6F2',
    colorWarningBg: shbColors.semantic.warningBg,
    colorWarningBorder: '#FBE3B8',
    colorErrorBg: shbColors.semantic.errorBg,
    colorErrorBorder: '#F6CFCB',
    colorSuccessBg: shbColors.semantic.successBg,
    colorSuccessBorder: '#BFE6D6',
    fontSize: 14,
    withDescriptionPadding: '14px 16px',
  },

  Table: {
    borderRadiusLG: shbRadius.large,
    headerBg: shbColors.orange[50],
    headerColor: shbColors.navy[700],
    headerSplitColor: 'transparent',
    rowHoverBg: shbColors.neutral.surfaceSoft,
    cellPaddingBlock: 12,
    cellPaddingInline: 14,
    fontSize: 14,
  },

  Tabs: {
    inkBarColor: shbColors.orange[500],
    itemSelectedColor: shbColors.navy[700],
    itemHoverColor: shbColors.orange[600],
    itemColor: shbColors.neutral.textSecondary,
    titleFontSize: 15,
    horizontalItemPadding: '10px 4px',
  },

  Avatar: {
    borderRadius: shbRadius.pill,
    colorTextPlaceholder: shbColors.navy[700],
  },

  Badge: {
    colorError: shbColors.orange[500],
  },

  Divider: {
    colorSplit: shbColors.neutral.border,
  },

  Empty: {
    colorTextDescription: shbColors.neutral.textMuted,
  },

  Result: {
    titleFontSize: 22,
  },

  Popconfirm: {
    borderRadiusLG: shbRadius.large,
  },

  Typography: {
    titleMarginBottom: '0.5em',
    titleMarginTop: '1.2em',
    fontFamilyCode: shbTypography.fontFamilyCode,
  },

  Spin: {
    colorPrimary: shbColors.orange[500],
  },

  Segmented: {
    itemSelectedBg: shbColors.neutral.white,
    itemSelectedColor: shbColors.navy[700],
    trackBg: shbColors.orange[50],
    borderRadius: shbRadius.medium,
  },
};
