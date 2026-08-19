import type { CSSProperties } from 'react';

import { brand } from '../theme';

/** Shared Descriptions styling so every detail panel reads identically. */
export const descStyles: { label: CSSProperties; content: CSSProperties } = {
  label: { color: brand.textFaint, fontSize: 12 },
  content: { color: brand.text, fontSize: 13 },
};
