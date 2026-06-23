import { useInfiniteQuery } from '@tanstack/react-query';

import { getLedger } from '../api/me';
import type { LedgerPage } from '../api/types';

export function useLedger() {
  return useInfiniteQuery<LedgerPage>({
    queryKey: ['ledger'],
    queryFn: ({ pageParam }) => getLedger(pageParam as string | undefined),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}
