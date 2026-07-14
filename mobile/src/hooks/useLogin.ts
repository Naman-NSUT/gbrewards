import { useMutation } from '@tanstack/react-query';

import { requestOtp, verifyOtp, type OtpRequestOut } from '../api/auth';
import type { TokenPair } from '../api/types';

// Step 1: send an OTP to the broker's phone (creating/refreshing their profile).
export function useRequestOtp() {
  return useMutation<OtpRequestOut, unknown, { phone: string; name: string; address: string }>({
    mutationFn: ({ phone, name, address }) => requestOtp(phone, name, address),
  });
}

// Step 2: verify the code and receive tokens.
export function useVerifyOtp() {
  return useMutation<TokenPair, unknown, { phone: string; code: string }>({
    mutationFn: ({ phone, code }) => verifyOtp(phone, code),
  });
}
