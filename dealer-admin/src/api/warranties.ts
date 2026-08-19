import { api } from './client';
import type { Page, WarrantyDetail, WarrantyListItem, WarrantySource } from './types';

export interface WarrantiesQuery {
  /** One box, matched against serial, customer mobile and invoice ref. */
  q?: string;
  status?: string;
  source?: WarrantySource;
  dealer_id?: string;
  dealer_code?: string;
  backdated?: boolean;
  unverified?: boolean;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listWarranties(params: WarrantiesQuery): Promise<Page<WarrantyListItem>> {
  const resp = await api.get<Page<WarrantyListItem>>('/dealer-admin/warranties', { params });
  return resp.data;
}

export async function getWarranty(id: string): Promise<WarrantyDetail> {
  const resp = await api.get<WarrantyDetail>(`/dealer-admin/warranties/${id}`);
  return resp.data;
}

/** Returns the warranty as it now stands — the reversal shows up in its ledger. */
export async function voidWarranty(
  id: string,
  body: { reason: string; clawback?: boolean; notify_customer?: boolean },
): Promise<WarrantyDetail> {
  const resp = await api.post<WarrantyDetail>(`/dealer-admin/warranties/${id}/void`, body);
  return resp.data;
}

export interface CustomerPatch {
  reason: string;
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  pincode?: string | null;
}

export async function updateWarrantyCustomer(
  id: string,
  body: CustomerPatch,
): Promise<WarrantyDetail> {
  const resp = await api.patch<WarrantyDetail>(`/dealer-admin/warranties/${id}/customer`, body);
  return resp.data;
}
