import { api } from './client';
import type { TokenPair } from './types';

export interface OtpRequestOut {
  resend_in: number;
}

/**
 * Ask for a login code.
 *
 * Always succeeds for a well-formed number, whether or not it belongs to a
 * dealer — the backend refuses to leak which numbers are provisioned. The
 * "we don't know this number" message therefore appears at verify time.
 */
export async function requestOtp(phone: string): Promise<OtpRequestOut> {
  const resp = await api.post<OtpRequestOut>('/dealer/auth/otp/request', { phone });
  return resp.data;
}

export async function verifyOtp(phone: string, code: string): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/dealer/auth/otp/verify', { phone, code });
  return resp.data;
}

export async function logout(refreshToken: string): Promise<void> {
  await api.post('/dealer/auth/logout', { refresh_token: refreshToken });
}
