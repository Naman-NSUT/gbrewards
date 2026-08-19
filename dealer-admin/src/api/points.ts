import { api } from './client';
import type { Page, PointRateRow, ProductRateRow } from './types';

/**
 * Registration points are set PER PRODUCT, mirroring how the worker programme
 * already prices assembly scans per product. Returns every product — including
 * ones with no rate yet, which are the rows that actually need attention: a
 * dealer registering an unpriced product earns nothing and will complain.
 */
export async function listProductRates(): Promise<ProductRateRow[]> {
  const resp = await api.get<ProductRateRow[]>('/dealer-admin/points/rates/current');
  return resp.data;
}

/** Every version ever opened, newest first. Filterable to one product. */
export async function listPointRates(params: {
  product_id?: string;
  limit?: number;
  offset?: number;
}): Promise<Page<PointRateRow>> {
  const resp = await api.get<Page<PointRateRow>>('/dealer-admin/points/rates', { params });
  return resp.data;
}

/**
 * Opens a NEW rate version for one product and closes that product's current
 * one. Historic ledger rows keep pointing at the version that priced them, so
 * this never reprices a registration that already happened.
 * Owner-only on the server (require_owner).
 */
export async function setPointRate(body: {
  product_id: string;
  points_per_registration: number;
  note?: string | null;
}): Promise<PointRateRow> {
  const resp = await api.post<PointRateRow>('/dealer-admin/points/rate', body);
  return resp.data;
}
