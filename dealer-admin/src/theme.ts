import { theme, type ThemeConfig } from 'antd';

/**
 * The GB Rewards admin skeleton — charcoal canvas, hairline borders, no glow —
 * with the accent swapped from their violet to GoodBed cyan. Same bones on
 * purpose: the client's team already knows where everything is, and a sibling
 * product should read as a sibling, not a clone.
 */
export const brand = {
  accent: '#0090D8',
  accentHover: '#2AA6E4',
  accentSoft: 'rgba(0,144,216,0.14)',
  // The GoodBed navy from the mattress logo. Used sparingly, as a ground for
  // accent-on-dark surfaces, so the dark panel still traces back to the brand.
  navy: '#184860',
  navyDeep: '#0E3346',

  canvas: '#0a0a0b',
  surface: '#141416',
  elevated: '#1a1a1d',

  border: 'rgba(255,255,255,0.09)',
  borderStrong: 'rgba(255,255,255,0.16)',

  text: '#ededef',
  textDim: '#8a8a93',
  textFaint: '#5c5c66',

  success: '#3fb37f',
  warning: '#d6a247',
  danger: '#e5648b',
  info: '#0090D8',

  mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
};

const FONT =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

const shadow = '0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -16px rgba(0,0,0,0.7)';

export const antdTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: brand.accent,
    colorInfo: brand.accent,
    colorSuccess: brand.success,
    colorWarning: brand.warning,
    colorError: brand.danger,
    colorBgBase: brand.canvas,
    colorBgLayout: brand.canvas,
    colorBgContainer: brand.surface,
    colorBgElevated: brand.elevated,
    colorBorder: brand.border,
    colorBorderSecondary: brand.border,
    colorText: brand.text,
    colorTextSecondary: brand.textDim,
    colorTextTertiary: brand.textFaint,
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    controlHeight: 36,
    fontFamily: FONT,
    fontSize: 14,
    wireframe: false,
    boxShadow: shadow,
    boxShadowSecondary: shadow,
    lineWidth: 1,
  },
  components: {
    Layout: {
      siderBg: brand.canvas,
      headerBg: 'rgba(10,10,11,0.8)',
      bodyBg: 'transparent',
      headerHeight: 56,
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: brand.accentSoft,
      darkItemSelectedColor: '#8fd3f6',
      darkItemColor: brand.textDim,
      darkItemHoverBg: 'rgba(255,255,255,0.035)',
      darkItemHoverColor: brand.text,
      itemBorderRadius: 7,
      itemMarginInline: 8,
      itemHeight: 38,
      iconSize: 16,
      fontSize: 13.5,
    },
    Card: { colorBgContainer: brand.surface, borderRadiusLG: 12, paddingLG: 20 },
    Table: {
      headerBg: 'transparent',
      headerColor: brand.textDim,
      headerSplitColor: 'transparent',
      borderColor: brand.border,
      rowHoverBg: 'rgba(255,255,255,0.025)',
      cellPaddingBlock: 12,
      cellPaddingInline: 14,
      fontSize: 13.5,
    },
    Button: {
      fontWeight: 550,
      primaryShadow: 'none',
      defaultBg: brand.elevated,
      defaultBorderColor: brand.border,
    },
    Input: { colorBgContainer: brand.elevated, activeBorderColor: brand.accent },
    InputNumber: { colorBgContainer: brand.elevated, activeBorderColor: brand.accent },
    Select: { colorBgContainer: brand.elevated, optionSelectedBg: brand.accentSoft },
    DatePicker: { colorBgContainer: brand.elevated, activeBorderColor: brand.accent },
    Segmented: { itemSelectedBg: brand.elevated, trackBg: 'rgba(255,255,255,0.04)' },
    Modal: { contentBg: brand.surface, headerBg: brand.surface },
    Drawer: { colorBgElevated: brand.surface },
    Tooltip: { colorBgSpotlight: brand.elevated, colorTextLightSolid: brand.text },
    Tag: { defaultBg: 'rgba(255,255,255,0.05)', defaultColor: brand.textDim },
    Tabs: { itemColor: brand.textDim, itemSelectedColor: brand.text, horizontalMargin: '0 0 16px 0' },
    Statistic: { contentFontSize: 28 },
    Descriptions: { labelBg: 'transparent', titleMarginBottom: 8 },
    Timeline: { dotBg: brand.surface, tailColor: brand.border },
    Progress: { defaultColor: brand.accent, remainingColor: 'rgba(255,255,255,0.07)' },
  },
};
