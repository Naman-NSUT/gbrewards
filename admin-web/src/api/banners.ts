import { api } from './client';
import type { Banner, BannerCreateInput, BannerUpdateInput } from './types';

export async function listBanners(): Promise<Banner[]> {
  const resp = await api.get<Banner[]>('/admin/banners');
  return resp.data;
}

// Build multipart form data. Only provided fields are appended, so a PATCH
// leaves untouched fields unchanged on the backend.
function toFormData(input: BannerCreateInput | BannerUpdateInput): FormData {
  const fd = new FormData();
  if (input.image) fd.append('image', input.image);
  if (input.caption !== undefined) fd.append('caption', input.caption);
  if (input.link_url !== undefined) fd.append('link_url', input.link_url);
  if (input.is_active !== undefined) fd.append('is_active', String(input.is_active));
  if (input.sort_order !== undefined) fd.append('sort_order', String(input.sort_order));
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
