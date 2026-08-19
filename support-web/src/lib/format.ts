import type { ClaimStatus, WarrantyStatus } from '../api/types';

const DIGITS = /\D/g;

/**
 * Mirrors `app.schemas.common.normalise_phone` so the customer is told about a
 * mistyped number instantly rather than after a round trip. The server still
 * validates — this is a courtesy, not a security boundary.
 */
export function normalisePhone(value: string): string | null {
  let digits = value.replace(DIGITS, '');
  if (digits.length === 12 && digits.startsWith('91')) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1);
  if (digits.length !== 10 || !'6789'.includes(digits[0]!)) return null;
  return `+91${digits}`;
}

/**
 * True if the string still carries redaction characters — used so the formatter
 * never mangles a masked value into something that looks real.
 *
 * The public API masks every customer on every response ("M**** I****",
 * "98****3210") and carries no flag saying so, so this sniff is the only test
 * there is — and the only one needed, because there is no unmasked case.
 */
export function looksMasked(value: string): boolean {
  return /[x*•]/i.test(value);
}

/**
 * Does a full mobile number agree with a fixed-width mask like `98****3210`?
 *
 * `true`/`false` when the mask is the shape the backend produces (first two and
 * last four digits of the local number), `null` when it cannot be read — an
 * unknown mask shape must not be turned into an accusation that the customer
 * typed the wrong number.
 *
 * This exists so a serial lookup can tell someone their number does not match
 * the record before they fill in a claim form and get a flat 404.
 */
export function phoneMatchesMask(phone: string, masked: string): boolean | null {
  const local = phone.replace(DIGITS, '').slice(-10);
  const parts = /^(\d{2})\*+(\d{4})$/.exec(masked.trim());
  if (local.length !== 10 || !parts) return null;
  return local.slice(0, 2) === parts[1] && local.slice(-4) === parts[2];
}

/** `+919812345678` -> `+91 98123 45678`. Masked values pass through untouched. */
export function formatPhone(value: string): string {
  if (looksMasked(value)) return value;
  const digits = value.replace(DIGITS, '');
  const local = digits.length === 12 && digits.startsWith('91') ? digits.slice(2) : digits;
  if (local.length !== 10) return value;
  return `+91 ${local.slice(0, 5)} ${local.slice(5)}`;
}

const DATE_FMT = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});

const DATETIME_FMT = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

/** Calendar dates arrive as `YYYY-MM-DD` and are NOT instants — parsing them
 *  with `new Date(str)` would treat them as UTC midnight and show the previous
 *  day to anyone west of Greenwich. Build the date from its parts instead. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const [y, m, d] = value.split('-').map(Number);
  if (!y || !m || !d) return value;
  return DATE_FMT.format(new Date(y, m - 1, d));
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : DATETIME_FMT.format(parsed);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatMonths(months: number): string {
  if (months % 12 === 0) {
    const years = months / 12;
    return years === 1 ? '1 year' : `${years} years`;
  }
  return `${months} months`;
}

export type Tone = 'success' | 'warning' | 'danger' | 'neutral';

export interface StatusMeta {
  label: string;
  tone: Tone;
  /** One line under the model name. Written for a customer, not an operator. */
  headline: string;
}

/**
 * The customer-facing vocabulary. Internal status names leak the mechanics of
 * the system ("pending_backdate" means nothing to a buyer), so every one of them
 * is translated exactly once, here.
 */
export function statusMeta(status: WarrantyStatus): StatusMeta {
  switch (status) {
    case 'active':
      return { label: 'Active', tone: 'success', headline: 'This warranty is valid.' };
    case 'expired':
      return {
        label: 'Expired',
        tone: 'neutral',
        headline: 'The warranty period for this mattress has ended.',
      };
    case 'voided':
      return {
        label: 'Cancelled',
        tone: 'danger',
        headline: 'This warranty was cancelled. Contact us if that is unexpected.',
      };
    case 'claimed':
      return {
        label: 'Claim raised',
        tone: 'warning',
        headline: 'A claim has been raised against this warranty.',
      };
    case 'pending_confirmation':
      return {
        label: 'Awaiting your confirmation',
        tone: 'warning',
        headline: 'Confirm your purchase to activate this warranty.',
      };
    case 'pending_review':
    case 'pending_backdate':
      return {
        label: 'Under review',
        tone: 'warning',
        headline: 'GoodBed is reviewing this registration. You will be contacted.',
      };
    default:
      return { label: status, tone: 'neutral', headline: '' };
  }
}

export function claimStatusMeta(status: ClaimStatus): StatusMeta {
  switch (status) {
    case 'open':
      return { label: 'Received', tone: 'warning', headline: 'We have your claim and it is queued.' };
    case 'in_review':
      return {
        label: 'In review',
        tone: 'warning',
        headline: 'Someone at GoodBed is looking at your claim.',
      };
    case 'approved':
      return { label: 'Approved', tone: 'success', headline: 'Your claim has been approved.' };
    case 'rejected':
      return { label: 'Not approved', tone: 'danger', headline: 'This claim was not approved.' };
    case 'closed':
      return { label: 'Closed', tone: 'neutral', headline: 'This claim is closed.' };
    default:
      return { label: status, tone: 'neutral', headline: '' };
  }
}

/**
 * Decide whether what was typed is a phone number or a serial.
 *
 * The rule is deliberately conservative: a value is only treated as a phone if
 * it is nothing but digits and separators AND normalises to a valid Indian
 * mobile. Everything else is a serial, because GB Rewards prints bare UUIDs and
 * a customer copying one in has no idea it is called a "serial".
 */
export function classifyQuery(raw: string): { kind: 'phone' | 'serial'; value: string } {
  const trimmed = raw.trim();
  if (/^[\d\s+()-]+$/.test(trimmed)) {
    const phone = normalisePhone(trimmed);
    if (phone) return { kind: 'phone', value: phone };
  }
  return { kind: 'serial', value: trimmed };
}
