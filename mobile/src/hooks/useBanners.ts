import { useQuery } from '@tanstack/react-query';

import { listBanners, type Banner } from '../api/banners';

export function useBanners() {
  return useQuery<Banner[]>({ queryKey: ['banners'], queryFn: listBanners });
}
