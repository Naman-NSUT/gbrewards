import type { Gender } from '../utils/profile';
import { api } from './client';
import type { TokenPair } from './types';

export interface OtpRequestOut {
  sent: boolean;
  resend_in: number;
}

/** Everything the sign-in screen collects, in the shape the API expects. */
export interface SignupProfile {
  phone: string;
  name: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  dob: string; // ISO yyyy-mm-dd
  gender: Gender;
}

// Step 1: upsert the broker by phone (with their profile) and send an OTP via SMS.
export async function requestOtp(profile: SignupProfile): Promise<OtpRequestOut> {
  const resp = await api.post<OtpRequestOut>('/auth/otp/request', profile);
  return resp.data;
}

// Step 2: verify the SMS code and receive access + refresh tokens.
export async function verifyOtp(phone: string, code: string): Promise<TokenPair> {
  const resp = await api.post<TokenPair>('/auth/otp/verify', { phone, code });
  return resp.data;
}
