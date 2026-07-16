import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createBanner,
  deleteBanner,
  listBanners,
  updateBanner,
} from '../api/banners';
import type { BannerInput } from '../api/types';

export function useBanners() {
  return useQuery({ queryKey: ['banners'], queryFn: listBanners });
}

export function useCreateBanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: BannerInput) => createBanner(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['banners'] }),
  });
}

export function useUpdateBanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<BannerInput> }) =>
      updateBanner(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['banners'] }),
  });
}

export function useDeleteBanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteBanner(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['banners'] }),
  });
}
