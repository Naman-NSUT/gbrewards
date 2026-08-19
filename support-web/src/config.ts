/** Empty base URL means "same origin", which is what a proxied deployment wants. */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');

export const API_PREFIX = '/api/v1';

/** Long enough for a slow 3G handshake, short enough that a dead backend does
 *  not leave a spinner running for a minute. */
export const REQUEST_TIMEOUT_MS = 20000;

export const SUPPORT_PHONE = (import.meta.env.VITE_SUPPORT_PHONE ?? '').trim();
export const SUPPORT_EMAIL = (import.meta.env.VITE_SUPPORT_EMAIL ?? '').trim();

/** Matches the server-side cap. Enforced here too so a customer on a slow
 *  connection is told before spending two minutes uploading. */
export const MAX_PROOF_BYTES = 5 * 1024 * 1024;

export const ACCEPTED_PROOF_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'application/pdf'];
