import { api } from './client';
import type { Admin } from './types';

export async function getMe(): Promise<Admin> {
  const resp = await api.get<Admin>('/admin/me');
  return resp.data;
}

export async function updateProfile(input: { name?: string; email?: string }): Promise<Admin> {
  const resp = await api.patch<Admin>('/admin/me', input);
  return resp.data;
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.post('/admin/me/password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}
