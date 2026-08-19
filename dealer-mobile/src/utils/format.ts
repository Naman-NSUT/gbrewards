import type { LedgerEntryType, WarrantyOut, WarrantyStatus } from '../api/types';

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/** "2026-08-15" -> "15 Aug 2026". Parsed by hand: `new Date('2026-08-15')` is
 *  UTC midnight, which renders as the previous day west of Greenwich. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const parts = iso.slice(0, 10).split('-');
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  const day = Number(parts[2]);
  if (!year || !month || !day) return iso;
  return `${day} ${MONTHS[month - 1] ?? ''} ${year}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  const hours = at.getHours();
  const minutes = `${at.getMinutes()}`.padStart(2, '0');
  const suffix = hours >= 12 ? 'pm' : 'am';
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${at.getDate()} ${MONTHS[at.getMonth()]} ${at.getFullYear()}, ${hour12}:${minutes}${suffix}`;
}

export function todayIso(): string {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, '0');
  const day = `${now.getDate()}`.padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

/** "15/08/2026" as the dealer types it, so the field never fights the keyboard. */
export function formatDateInput(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

/** "15/08/2026" -> "2026-08-15", or null when it is not a real date. */
export function parseDateInput(value: string): string | null {
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value.trim());
  if (!match) return null;
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  const probe = new Date(year, month - 1, day);
  if (probe.getMonth() !== month - 1 || probe.getDate() !== day) return null;
  return `${year}-${`${month}`.padStart(2, '0')}-${`${day}`.padStart(2, '0')}`;
}

export function formatPoints(points: number): string {
  return points.toLocaleString('en-IN');
}

/** Warranty end date in the past. Derived here exactly as it is server-side —
 *  `expired` is not a stored status anywhere in this product. */
export function isExpired(warranty: Pick<WarrantyOut, 'warranty_end_date'>): boolean {
  return warranty.warranty_end_date < todayIso();
}

export type DisplayStatus = WarrantyStatus | 'expired';

export function displayStatus(warranty: WarrantyOut): DisplayStatus {
  if (warranty.status === 'active' && isExpired(warranty)) return 'expired';
  return warranty.status;
}

export const STATUS_LABEL: Record<DisplayStatus, string> = {
  pending_confirmation: 'Awaiting customer',
  pending_review: 'In review',
  pending_backdate: 'Awaiting approval',
  active: 'Active',
  claimed: 'Claimed',
  voided: 'Voided',
  expired: 'Expired',
};

/** Plain English for the ledger. "registration_credit" means nothing at a counter. */
export const LEDGER_LABEL: Record<LedgerEntryType, string> = {
  registration_credit: 'Sale registered',
  registration_reversal: 'Registration cancelled',
  redemption_debit: 'Reward redeemed',
  redemption_release: 'Redemption returned',
  admin_credit: 'Adjustment by GoodBed',
  admin_debit: 'Adjustment by GoodBed',
};
