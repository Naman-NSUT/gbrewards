import { api } from './client';
import type { ApprovalCounts, ApprovalItem, ApprovalStatus, Page, WarrantyDetail } from './types';

export interface ApprovalsQuery {
  /** The queue is split by warranty status, not by a separate "kind". */
  status?: ApprovalStatus;
  dealer_id?: string;
  limit?: number;
  offset?: number;
}

export async function listApprovals(params: ApprovalsQuery): Promise<Page<ApprovalItem>> {
  const resp = await api.get<Page<ApprovalItem>>('/dealer-admin/approvals', { params });
  return resp.data;
}

/** The badge counts live on their own endpoint, not on the list response. */
export async function getApprovalCounts(): Promise<ApprovalCounts> {
  const resp = await api.get<ApprovalCounts>('/dealer-admin/approvals/count');
  return resp.data;
}

export async function approveWarranty(
  warrantyId: string,
  body: { reason: string; honour_requested_date?: boolean },
): Promise<WarrantyDetail> {
  const resp = await api.post<WarrantyDetail>(`/dealer-admin/approvals/${warrantyId}/approve`, body);
  return resp.data;
}

/** Rejection voids the warranty — the reason is mandatory and lands on the audit row. */
export async function rejectWarranty(
  warrantyId: string,
  body: { reason: string },
): Promise<WarrantyDetail> {
  const resp = await api.post<WarrantyDetail>(`/dealer-admin/approvals/${warrantyId}/reject`, body);
  return resp.data;
}
