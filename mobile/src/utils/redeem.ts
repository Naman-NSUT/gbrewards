/** Mirrors the server's per-request ceiling (`redemption.MAX_QUANTITY`). */
export const MAX_QUANTITY = 999;

/**
 * How many of a reward the balance can actually cover.
 *
 * This is the slider's ceiling, and it has to agree with what the server will
 * accept — offering a quantity and then refusing it is the one outcome worth
 * avoiding. Returns 0 when nothing is affordable, so the caller can disable the
 * button rather than show a slider that cannot move.
 */
export function maxRedeemableQuantity(available: number, pointsCost: number): number {
  // A reward priced at zero would divide to Infinity. The server refuses those
  // outright, so there is nothing to offer.
  if (pointsCost <= 0) return 0;
  if (available < pointsCost) return 0;
  return Math.min(Math.floor(available / pointsCost), MAX_QUANTITY);
}

/**
 * Keep a chosen quantity inside what is affordable right now.
 *
 * The balance moves while the screen is open — a scan lands, another request is
 * approved — so a quantity picked a moment ago can go out of range.
 */
export function clampQuantity(quantity: number, maxQuantity: number): number {
  if (maxQuantity < 1) return 1;
  return Math.min(Math.max(Math.round(quantity), 1), maxQuantity);
}
