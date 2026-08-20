import { api } from './client';
import type { TokenPair } from './types';

export interface OtpRequestOut {
  resend_in: number;
  /** True when the code will finish creating a new shop rather than sign in. */
  is_new_account?: boolean;
  /** False when this number has no account — offer signup instead of waiting. */
  account_exists?: boolean;
}

export interface SignupInput {
  phone: string;
  /** The person signing up; they become the shop's owner. */
  name: string;
  shop_name: string;
  city?: string;
  address?: string;
  pincode?: string;
  gst_number?: string;
}

/**
 * Start creating a shop account.
 *
 * The details are held server-side against the code and only become a real
 * dealership once verifyOtp succeeds — so abandoning this screen leaves nothing
 * behind. 409 means the number already has an account and should sign in.
 */
export async function signup(input: SignupInput): Promise<OtpRequestOut> {
  const resp = await api.post<OtpRequestOut>('/dealer/auth/signup', input);
  return resp.data;
}

/**
 * Ask for a login code.
 *
 * Returns account_exists: false when the number has no account, so the caller
 * can send them to signup rather than waiting for a code that was never sent.
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
