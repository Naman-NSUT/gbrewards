import { api } from './client';
import type { TokenPair } from './types';

// Direct login: the phone number is the identity. Creates the broker on first
// login, refreshes name + address on every login. No OTP.
export async function login(
  phone: string,
  name: string,
  address: string
): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/login', { phone, name, address });
  return resp.data;
}
