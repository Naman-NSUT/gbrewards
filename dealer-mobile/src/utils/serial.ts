/**
 * Mirrors backend `normalise_serial`, and is used for ONE thing: building the
 * preview URL.
 *
 * The QR may encode a bare serial today and a URL tomorrow — a URL would carry
 * slashes that cannot survive a path parameter, so the last segment is taken
 * here before the request is built. The registration body still carries the RAW
 * scanned string: the backend owns the payload format, and a client that
 * pre-parses it is a client that silently breaks the day that format changes.
 */
export function normaliseSerial(raw: string): string {
  let value = (raw ?? '').trim();
  if (!value) return '';
  if (value.includes('://')) {
    value = value.split('?')[0]?.split('#')[0] ?? '';
    const segments = value.split('/').filter(Boolean);
    value = segments[segments.length - 1] ?? '';
  }
  return value.toLowerCase();
}

/** Serials are long (a bare UUID). Rows show head and tail, never a wrapped blob. */
export function shortSerial(serial: string): string {
  const value = normaliseSerial(serial);
  if (value.length <= 16) return value.toUpperCase();
  return `${value.slice(0, 8)}…${value.slice(-4)}`.toUpperCase();
}
