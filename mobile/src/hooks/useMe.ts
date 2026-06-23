import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getMe, updateName } from '../api/me';
import type { Me } from '../api/types';

export function useMe() {
  return useQuery<Me>({ queryKey: ['me'], queryFn: getMe });
}

export function useUpdateName() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => updateName(name),
    onSuccess: (me) => {
      qc.setQueryData(['me'], me);
    },
  });
}
