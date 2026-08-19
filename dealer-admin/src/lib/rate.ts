export type RateTone = 'critical' | 'warn' | 'ok' | 'good';

/**
 * Where the thresholds sit, and why.
 *
 * Below 40% the shop is effectively not on the programme and needs a phone
 * call; below 70% it is registering some sales and forgetting others, which is
 * a training problem, not an enforcement one. Above 90% is what "working" looks
 * like. These are the bands the client's account managers already think in.
 */
export function rateTone(rate: number): RateTone {
  if (rate < 0.4) return 'critical';
  if (rate < 0.7) return 'warn';
  if (rate < 0.9) return 'ok';
  return 'good';
}
