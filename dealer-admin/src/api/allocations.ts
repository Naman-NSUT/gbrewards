import { api } from './client';
import type {
  Allocation,
  AllocationBatch,
  AllocationStatus,
  AllocationUploadResult,
  Page,
} from './types';

export interface AllocationsQuery {
  dealer_id?: string;
  dealer_code?: string;
  status?: AllocationStatus;
  /** Exact-ish serial match — there is no free-text `q` on this endpoint. */
  serial?: string;
  batch_id?: string;
  limit?: number;
  offset?: number;
}

export async function listAllocations(params: AllocationsQuery): Promise<Page<Allocation>> {
  const resp = await api.get<Page<Allocation>>('/dealer-admin/allocations', { params });
  return resp.data;
}

/** Dry run. Nothing is written — the admin sees what WOULD happen, then commits. */
export async function previewAllocationCsv(file: File): Promise<AllocationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  const resp = await api.post<AllocationUploadResult>('/dealer-admin/allocations/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return resp.data;
}

export async function uploadAllocationCsv(file: File): Promise<AllocationUploadResult> {
  const form = new FormData();
  form.append('file', file);
  const resp = await api.post<AllocationUploadResult>('/dealer-admin/allocations/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return resp.data;
}

export async function listAllocationBatches(params: {
  limit?: number;
  offset?: number;
}): Promise<Page<AllocationBatch>> {
  const resp = await api.get<Page<AllocationBatch>>('/dealer-admin/allocations/batches', { params });
  return resp.data;
}

export async function getAllocationBatch(batchId: string): Promise<AllocationBatch> {
  const resp = await api.get<AllocationBatch>(`/dealer-admin/allocations/batches/${batchId}`);
  return resp.data;
}

export async function revokeAllocation(id: string, body: { reason: string }): Promise<Allocation> {
  const resp = await api.post<Allocation>(`/dealer-admin/allocations/${id}/revoke`, body);
  return resp.data;
}
