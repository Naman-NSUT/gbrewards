/**
 * Client-side twin of backend `app/schemas/common.normalise_phone`.
 *
 * Validated here as well as on the server because the customer is standing at
 * the counter: a typo caught before submit costs three seconds, and a typo
 * caught after submit means the warranty SMS goes to a stranger and the record
 * is attached to the wrong person.
 */
const NON_DIGITS = /\D/g;

export function digitsOf(value: string): string {
  return (value ?? '').replace(NON_DIGITS, '');
}

/** Returns E.164 (+91XXXXXXXXXX), or null when the number cannot be valid. */
export function normalisePhone(value: string): string | null {
  let digits = digitsOf(value);
  if (digits.length === 12 && digits.startsWith('91')) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith('0')) digits = digits.slice(1);
  if (digits.length !== 10) return null;
  if (!'6789'.includes(digits[0] ?? '')) return null;
  return `+91${digits}`;
}

export function isValidPhone(value: string): boolean {
  return normalisePhone(value) !== null;
}

/**
 * Show enough for the dealer to confirm they typed the right number back to the
 * customer, without printing a full mobile number on a shop-floor screen.
 */
export function maskPhone(value: string | null | undefined): string {
  const digits = digitsOf(value ?? '');
  if (digits.length < 4) return '—';
  return `+91 •••••${digits.slice(-5)}`;
}

/** Display form for a number we trust: +91 98765 43210. */
export function formatPhone(value: string | null | undefined): string {
  const digits = digitsOf(value ?? '');
  const local = digits.length > 10 ? digits.slice(-10) : digits;
  if (local.length !== 10) return value ?? '—';
  return `+91 ${local.slice(0, 5)} ${local.slice(5)}`;
}
