import { api } from './client';
import type { AdminTokenPair } from './types';

export async function login(email: string, password: string): Promise<AdminTokenPair> {
  const resp = await api.post<AdminTokenPair>('/admin/auth/login', { email, password });
  return resp.data;
}
