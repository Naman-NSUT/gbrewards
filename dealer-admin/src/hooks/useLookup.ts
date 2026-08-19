import { useQuery } from '@tanstack/react-query';

import { lookupSerial } from '../api/lookup';
import { qk } from './keys';

export function useSerialLookup(serial: string) {
  const trimmed = serial.trim();
  return useQuery({
    queryKey: qk.lookupSerial(trimmed),
    queryFn: () => lookupSerial(trimmed),
    enabled: trimmed.length > 0,
    // Support reads this while the customer is still talking; a stale answer
    // three minutes into the call is worse than a second request.
    staleTime: 0,
  });
}
