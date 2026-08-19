import { api } from './client';
import type { Page } from './types';

/**
 * The dealer programme's own product catalogue and serials.
 *
 * These are NOT the factory's products or QR codes. The dealer app scans a
 * dealer label, so the dealer panel mints and prints its own — a mattress ends
 * up carrying two QR codes, one per programme.
 */
export interface DealerProduct {
  id: string;
  name: string;
  description: string | null;
  terms: string | null;
  model_code: string | null;
  warranty_months: number;
  is_active: boolean;
  units_generated: number;
}

export interface DealerProductInput {
  name: string;
  description?: string | null;
  terms?: string | null;
  model_code?: string | null;
  warranty_months: number;
  is_active: boolean;
}

export interface QrBatch {
  id: string;
  product_id: string;
  quantity: number;
  label: string | null;
  created_at: string;
}

export async function listProducts(params: {
  q?: string;
  is_active?: boolean;
  limit?: number;
  offset?: number;
}): Promise<Page<DealerProduct>> {
  const resp = await api.get<Page<DealerProduct>>('/dealer-admin/products', { params });
  return resp.data;
}

export async function createProduct(body: DealerProductInput): Promise<DealerProduct> {
  const resp = await api.post<DealerProduct>('/dealer-admin/products', body);
  return resp.data;
}

export async function updateProduct(
  id: string,
  body: DealerProductInput,
): Promise<DealerProduct> {
  const resp = await api.patch<DealerProduct>(`/dealer-admin/products/${id}`, body);
  return resp.data;
}

/** Mints `quantity` new serials. There is no undo — void individual labels instead. */
export async function generateBatch(
  productId: string,
  body: { quantity: number; label?: string | null },
): Promise<QrBatch> {
  const resp = await api.post<QrBatch>(`/dealer-admin/products/${productId}/batches`, body);
  return resp.data;
}

export async function listBatches(params: {
  product_id?: string;
  limit?: number;
  offset?: number;
}): Promise<Page<QrBatch>> {
  const resp = await api.get<Page<QrBatch>>('/dealer-admin/batches', { params });
  return resp.data;
}

/** The printable sheet. Downloaded as a blob so the auth header is still sent. */
export async function downloadLabels(batchId: string): Promise<Blob> {
  const resp = await api.get(`/dealer-admin/batches/${batchId}/labels.pdf`, {
    responseType: 'blob',
  });
  return resp.data as Blob;
}
