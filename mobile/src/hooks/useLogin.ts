import { useMutation } from '@tanstack/react-query';

import { login } from '../api/auth';
import type { TokenPair } from '../api/types';

export function useLogin() {
  return useMutation<TokenPair, unknown, { phone: string; name: string; address: string }>({
    mutationFn: ({ phone, name, address }) => login(phone, name, address),
  });
}
