import { useMutation } from '@tanstack/react-query';

import { requestOtp, verifyOtp } from '../api/auth';
import type { TokenPair } from '../api/types';

export function useRequestOtp() {
  return useMutation({
    mutationFn: ({ phone, name }: { phone: string; name?: string }) =>
      requestOtp(phone, name),
  });
}

export function useVerifyOtp() {
  return useMutation<TokenPair, unknown, { phone: string; code: string }>({
    mutationFn: ({ phone, code }) => verifyOtp(phone, code),
  });
}
