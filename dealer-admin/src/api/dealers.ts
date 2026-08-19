import { api } from './client';
import type {
  Dealer,
  DealerDetail,
  DealerInput,
  DealerLedger,
  DealerListItem,
  DealerStatus,
  Ok,
  Page,
  PointsSummary,
  StaffInput,
  StaffRow,
  AdjustResult,
} from './types';

export interface DealersQuery {
  q?: string;
  status?: DealerStatus;
  limit?: number;
  offset?: number;
}

export async function listDealers(params: DealersQuery): Promise<Page<DealerListItem>> {
  const resp = await api.get<Page<DealerListItem>>('/dealer-admin/dealers', { params });
  return resp.data;
}

export async function getDealer(id: string): Promise<DealerDetail> {
  const resp = await api.get<DealerDetail>(`/dealer-admin/dealers/${id}`);
  return resp.data;
}

export async function createDealer(body: DealerInput): Promise<Dealer> {
  const resp = await api.post<Dealer>('/dealer-admin/dealers', body);
  return resp.data;
}

export async function updateDealer(id: string, body: Partial<DealerInput>): Promise<Dealer> {
  const resp = await api.patch<Dealer>(`/dealer-admin/dealers/${id}`, body);
  return resp.data;
}

export async function suspendDealer(id: string, body: { reason: string }): Promise<Dealer> {
  const resp = await api.post<Dealer>(`/dealer-admin/dealers/${id}/suspend`, body);
  return resp.data;
}

/** Reactivate, not "reinstate" — the server's word, so logs and UI agree. */
export async function reactivateDealer(id: string): Promise<Dealer> {
  const resp = await api.post<Dealer>(`/dealer-admin/dealers/${id}/reactivate`);
  return resp.data;
}

export async function listDealerStaff(
  dealerId: string,
  params: { include_inactive?: boolean } = {},
): Promise<StaffRow[]> {
  const resp = await api.get<StaffRow[]>(`/dealer-admin/dealers/${dealerId}/staff`, { params });
  return resp.data;
}

export async function createDealerStaff(dealerId: string, body: StaffInput): Promise<StaffRow> {
  const resp = await api.post<StaffRow>(`/dealer-admin/dealers/${dealerId}/staff`, body);
  return resp.data;
}

export async function updateDealerStaff(
  dealerId: string,
  staffId: string,
  body: { name?: string | null; role?: string | null; is_active?: boolean | null },
): Promise<StaffRow> {
  const resp = await api.patch<StaffRow>(`/dealer-admin/dealers/${dealerId}/staff/${staffId}`, body);
  return resp.data;
}

export async function deleteDealerStaff(dealerId: string, staffId: string): Promise<Ok> {
  const resp = await api.delete<Ok>(`/dealer-admin/dealers/${dealerId}/staff/${staffId}`);
  return resp.data;
}

export async function getDealerPoints(dealerId: string): Promise<PointsSummary> {
  const resp = await api.get<PointsSummary>(`/dealer-admin/dealers/${dealerId}/points`);
  return resp.data;
}

/** The ledger is per dealer: there is no global ledger feed on the server. */
export async function getDealerLedger(
  dealerId: string,
  params: { limit?: number; offset?: number },
): Promise<DealerLedger> {
  const resp = await api.get<DealerLedger>(`/dealer-admin/dealers/${dealerId}/ledger`, { params });
  return resp.data;
}

/** `amount` is signed: positive credits the dealer, negative debits them. */
export async function adjustDealerPoints(
  dealerId: string,
  body: { amount: number; reason: string },
): Promise<AdjustResult> {
  const resp = await api.post<AdjustResult>(`/dealer-admin/dealers/${dealerId}/points/adjust`, body);
  return resp.data;
}
