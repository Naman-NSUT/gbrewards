import { useQuery } from '@tanstack/react-query';

import { fetchProfile } from '../api/auth';
import { useAuth } from '../auth/AuthContext';
import { qk } from './keys';

/**
 * Enriches the JWT-derived identity with the admin's real name and email.
 * Deliberately non-retrying and non-blocking: the panel is fully usable from
 * the token's claims alone, so a hiccup here must never gate the UI.
 */
export function useAdminProfile() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: qk.me,
    queryFn: fetchProfile,
    enabled: isAuthenticated,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
