import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createBanner,
  deleteBanner,
  listBanners,
  updateBanner,
} from '../api/banners';
import type { BannerCreateInput, BannerUpdateInput } from '../api/types';

export function useBanners() {
  return useQuery({ queryKey: ['banners'], queryFn: listBanners });
}

export function useCreateBanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: BannerCreateInput) => createBanner(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['banners'] }),
  });
}

export function useUpdateBanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: BannerUpdateInput }) =>
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
