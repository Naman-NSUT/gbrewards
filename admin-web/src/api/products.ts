import { api } from './client';
import type { Batch, OrderResult, Product, ProductWithCounts } from './types';

export interface OrderItem {
  product_id: string;
  quantity: number;
}

export interface ProductInput {
  name: string;
  description?: string | null;
  points_value: number;
  is_active?: boolean;
}

export async function listProducts(): Promise<Product[]> {
  const resp = await api.get<Product[]>('/admin/products');
  return resp.data;
}

export async function createProduct(input: ProductInput): Promise<Product> {
  const resp = await api.post<Product>('/admin/products', input);
  return resp.data;
}

export async function getProduct(id: string): Promise<ProductWithCounts> {
  const resp = await api.get<ProductWithCounts>(`/admin/products/${id}`);
  return resp.data;
}

export async function updateProduct(id: string, input: Partial<ProductInput>): Promise<Product> {
  const resp = await api.patch<Product>(`/admin/products/${id}`, input);
  return resp.data;
}

export async function deleteProduct(id: string): Promise<void> {
  await api.delete(`/admin/products/${id}`);
}

export async function createBatch(
  productId: string,
  quantity: number,
  label?: string,
): Promise<Batch> {
  const resp = await api.post<Batch>(`/admin/products/${productId}/batches`, { quantity, label });
  return resp.data;
}

export async function downloadBatchPdf(batchId: string): Promise<Blob> {
  const resp = await api.get(`/admin/batches/${batchId}/export`, {
    params: { format: 'pdf' },
    responseType: 'blob',
  });
  return resp.data as Blob;
}

export async function createOrder(items: OrderItem[], label?: string): Promise<OrderResult> {
  const resp = await api.post<OrderResult>('/admin/orders', { items, label });
  return resp.data;
}

export async function downloadOrderPdf(batchIds: string[]): Promise<Blob> {
  const params = new URLSearchParams();
  batchIds.forEach((id) => params.append('ids', id));
  params.append('format', 'pdf');
  const resp = await api.get(`/admin/orders/export?${params.toString()}`, {
    responseType: 'blob',
  });
  return resp.data as Blob;
}
