import { api } from './client';
import type { Banner, BannerCreateInput, BannerUpdateInput } from './types';

export async function listBanners(): Promise<Banner[]> {
  const resp = await api.get<Banner[]>('/admin/banners');
  return resp.data;
}

/**
 * Append a field only when it carries a value.
 *
 * Guarding on `!== undefined` alone was not enough: antd's InputNumber and Input
 * hand back `null` for a cleared field, and `String(null)` is the four-letter
 * text "null". That reached the server as a literal value — a 422 on the numeric
 * and boolean fields, and worse on the text ones, where a banner would silently
 * save with the caption "null".
 *
 * Omitting the field instead lets the backend apply its own default on create,
 * and leaves the stored value untouched on a PATCH.
 */
function appendIfSet(fd: FormData, key: string, value: unknown): void {
  if (value === undefined || value === null) return;
  fd.append(key, value instanceof Blob ? value : String(value));
}

// Build multipart form data. Only provided fields are appended, so a PATCH
// leaves untouched fields unchanged on the backend.
function toFormData(input: BannerCreateInput | BannerUpdateInput): FormData {
  const fd = new FormData();
  appendIfSet(fd, 'image', input.image);
  appendIfSet(fd, 'caption', input.caption);
  appendIfSet(fd, 'link_url', input.link_url);
  appendIfSet(fd, 'is_active', input.is_active);
  appendIfSet(fd, 'sort_order', input.sort_order);
  return fd;
}

export async function createBanner(input: BannerCreateInput): Promise<Banner> {
  // axios strips the default JSON content-type for FormData and sets the
  // multipart boundary itself in the browser.
  const resp = await api.post<Banner>('/admin/banners', toFormData(input));
  return resp.data;
}

export async function updateBanner(id: string, input: BannerUpdateInput): Promise<Banner> {
  const resp = await api.patch<Banner>(`/admin/banners/${id}`, toFormData(input));
  return resp.data;
}

export async function deleteBanner(id: string): Promise<void> {
  await api.delete(`/admin/banners/${id}`);
}

/** Exposed for tests: the multipart conversion is where banner saves go wrong. */
export const __testing = { toFormData };
