import { api } from './client';
import type { Page } from './types';

/**
 * The dealer programme's own product catalogue.
 *
 * These are NOT the factory's products. A dealer registering a sale picks one
 * of these from a dropdown and types their invoice number — nothing is scanned
 * and nothing is printed, so a product no longer carries serials of its own.
 */
export interface DealerProduct {
  id: string;
  name: string;
  description: string | null;
  terms: string | null;
  model_code: string | null;
  warranty_months: number;
  is_active: boolean;
}

export interface DealerProductInput {
  name: string;
  description?: string | null;
  terms?: string | null;
  model_code?: string | null;
  warranty_months: number;
  is_active: boolean;
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
