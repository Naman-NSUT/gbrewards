import { brand } from '../../theme';

export const axisTick = { fill: brand.textDim, fontSize: 11 };
export const gridStroke = 'rgba(255,255,255,0.06)';

export function shortDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
