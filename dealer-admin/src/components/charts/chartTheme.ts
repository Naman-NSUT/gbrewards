import { brand } from '../../theme';

export const axisTick = { fill: brand.textDim, fontSize: 11 };
export const gridStroke = 'rgba(255,255,255,0.06)';

/** Series colours. Dealer registrations are the accent — they are the product.
 *  Self-registrations are pink because each one is a dealer who did not do the
 *  job, and the chart should say so without a legend. */
export const SERIES = {
  dealer: brand.accent,
  self: brand.danger,
  points: brand.textDim,
};

export function shortDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
