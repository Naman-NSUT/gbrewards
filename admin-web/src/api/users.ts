

import { api } from './client';
import type { AdminUserDetail, LedgerPage, UserListPage } from './types';

export async function listUsers(params: {
  q?: string;
  cursor?: string;
  limit?: number;
}): Promise<UserListPage> {
  const resp = await api.get<UserListPage>('/admin/users', { params });
  return resp.data;
}

export async function getUser(id: string): Promise<AdminUserDetail> {
  const resp = await api.get<AdminUserDetail>(`/admin/users/${id}`);
  return resp.data;
}

export async function getUserLedger(
  id: string,
  params: { cursor?: string; limit?: number },
): Promise<LedgerPage> {
  const resp = await api.get<LedgerPage>(`/admin/users/${id}/ledger`, { params });
  return resp.data;
}

export async function creditUser(
  id: string,
  points: number,
  note?: string,
): Promise<AdminUserDetail> {
  const resp = await api.post<AdminUserDetail>(`/admin/users/${id}/credit`, { points, note });
  return resp.data;
}

export async function debitUser(
  id: string,
  points: number,
  note?: string,
): Promise<AdminUserDetail> {
  const resp = await api.post<AdminUserDetail>(`/admin/users/${id}/debit`, { points, note });
  return resp.data;
}

export async function setUserActive(id: string, isActive: boolean): Promise<AdminUserDetail> {
  const resp = await api.patch<AdminUserDetail>(`/admin/users/${id}`, { is_active: isActive });
  return resp.data;
}
