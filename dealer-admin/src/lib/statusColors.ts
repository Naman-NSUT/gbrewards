import { brand } from '../theme';

/**
 * One colour vocabulary for every status in the product, so `active` means the
 * same green on the warranties table, the lookup screen and the dashboard.
 *
 * Amber is always "a human owes this a decision", pink is always "this ended
 * badly", grey is always "no longer in play".
 */
const COLORS: Record<string, string> = {
  // warranty
  active: brand.success,
  claimed: brand.accent,
  voided: brand.textFaint,
  expired: brand.textFaint,
  pending_confirmation: brand.warning,
  pending_review: brand.warning,
  pending_backdate: brand.warning,
  registered: brand.success,
  returned: brand.textFaint,
  // claim
  open: brand.warning,
  in_review: brand.accent,
  approved: brand.success,
  rejected: brand.danger,
  closed: brand.textFaint,
  // redemption
  pending: brand.warning,
  fulfilled: brand.success,
  cancelled: brand.textFaint,
  // sms
  queued: brand.warning,
  sent: brand.accent,
  delivered: brand.success,
  failed: brand.danger,
  undelivered: brand.danger,
  // dealer / staff
  suspended: brand.danger,
  inactive: brand.textFaint,
};

export function statusColor(status: string): string {
  return COLORS[status] ?? brand.textDim;
}
