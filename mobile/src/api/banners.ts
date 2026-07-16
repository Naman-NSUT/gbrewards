import { API_BASE_URL, API_PREFIX } from '../config';
import { api } from './client';

export interface Banner {
  id: string;
  image_url: string;
  caption: string | null;
  link_url: string | null;
  sort_order: number;
}

export async function listBanners(): Promise<Banner[]> {
  const resp = await api.get<Banner[]>('/catalog/banners');
  return resp.data;
}

// Backend origin = API base URL without the '/api/v1' prefix. `image_url` may be
// absolute (http…) — returned unchanged — or a relative '/…' path that must be
// resolved against that origin.
const ORIGIN = API_BASE_URL.endsWith(API_PREFIX)
  ? API_BASE_URL.slice(0, -API_PREFIX.length)
  : API_BASE_URL;

export function resolveBannerUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  return `${ORIGIN}${url.startsWith('/') ? '' : '/'}${url}`;
}
