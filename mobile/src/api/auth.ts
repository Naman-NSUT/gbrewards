import { api } from './client';
import type { TokenPair } from './types';

export async function requestOtp(phone: string, name?: string): Promise<void> {
  await api.post('/auth/otp/request', { phone, name });
}

export async function verifyOtp(phone: string, code: string): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/otp/verify', { phone, code });
  return resp.data;
}
