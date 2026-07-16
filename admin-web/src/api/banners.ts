import { api } from './client';
import type { Banner, BannerInput } from './types';

export async function listBanners(): Promise<Banner[]> {
  const resp = await api.get<Banner[]>('/admin/banners');
  return resp.data;
}

export async function createBanner(input: BannerInput): Promise<Banner> {
  const resp = await api.post<Banner>('/admin/banners', input);
  return resp.data;
}

export async function updateBanner(id: string, input: Partial<BannerInput>): Promise<Banner> {
  const resp = await api.patch<Banner>(`/admin/banners/${id}`, input);
  return resp.data;
}

export async function deleteBanner(id: string): Promise<void> {
  await api.delete(`/admin/banners/${id}`);
}
