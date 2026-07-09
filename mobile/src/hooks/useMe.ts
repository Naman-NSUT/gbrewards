import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getMe, updateProfile, type ProfileUpdate } from '../api/me';
import type { Me } from '../api/types';

export function useMe() {
  return useQuery<Me>({ queryKey: ['me'], queryFn: getMe });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProfileUpdate) => updateProfile(payload),
    onSuccess: (me) => {
      qc.setQueryData(['me'], me);
    },
  });
}
