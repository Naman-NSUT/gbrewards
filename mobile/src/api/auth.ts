import { api } from './client';
import type { TokenPair } from './types';

export interface OtpRequestOut {
  sent: boolean;
  resend_in: number;
}

// Step 1: upsert the broker by phone (with name + address) and send an OTP via SMS.
export async function requestOtp(
  phone: string,
  name: string,
  address: string
): Promise<OtpRequestOut> {
  const resp = await api.post<OtpRequestOut>('/auth/otp/request', { phone, name, address });
  return resp.data;
}

// Step 2: verify the SMS code and receive access + refresh tokens.
export async function verifyOtp(phone: string, code: string): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/otp/verify', { phone, code });
  return resp.data;
}
