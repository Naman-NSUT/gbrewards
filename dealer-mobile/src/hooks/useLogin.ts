import { useMutation } from '@tanstack/react-query';

import { requestOtp, verifyOtp, type OtpRequestOut } from '../api/auth';
import type { TokenPair } from '../api/types';

export function useRequestOtp() {
  return useMutation<OtpRequestOut, unknown, string>({
    mutationFn: (phone: string) => requestOtp(phone),
  });
}

export function useVerifyOtp() {
  return useMutation<TokenPair, unknown, { phone: string; code: string }>({
    mutationFn: ({ phone, code }) => verifyOtp(phone, code),
  });
}
