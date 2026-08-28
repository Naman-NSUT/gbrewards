import { useQuery } from '@tanstack/react-query';

import { listBanners } from '../api/banners';

/**
 * Marketing artwork, not transactional data: a stale poster costs nothing, and
 * a dealer opening the app at a counter should not wait on it. Long stale time,
 * and the carousel renders nothing at all until it has something to show.
 */
export function useBanners() {
  return useQuery({
    queryKey: ['banners'],
    queryFn: listBanners,
    staleTime: 10 * 60 * 1000,
  });
}
