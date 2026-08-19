import { api } from './client';
import type { ClaimDetail, ClaimListItem, ClaimStatus, Page } from './types';

export interface ClaimsQuery {
  status?: ClaimStatus;
  q?: string;
  dealer_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listClaims(params: ClaimsQuery): Promise<Page<ClaimListItem>> {
  const resp = await api.get<Page<ClaimListItem>>('/dealer-admin/claims', { params });
  return resp.data;
}

/** The only endpoint that returns `resolution_note`. */
export async function getClaim(id: string): Promise<ClaimDetail> {
  const resp = await api.get<ClaimDetail>(`/dealer-admin/claims/${id}`);
  return resp.data;
}

export async function updateClaim(
  id: string,
  body: { status: ClaimStatus; resolution_note?: string | null },
): Promise<ClaimDetail> {
  const resp = await api.patch<ClaimDetail>(`/dealer-admin/claims/${id}`, body);
  return resp.data;
}
