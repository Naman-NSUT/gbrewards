import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getSmsTemplates, listSms, retrySms, type SmsQuery } from '../api/sms';
import { qk } from './keys';

export function useSmsLog(params: SmsQuery) {
  return useQuery({
    queryKey: qk.smsList(params),
    queryFn: () => listSms(params),
    placeholderData: keepPreviousData,
  });
}

/** The registry drives the template filter, so the options can never list a
 *  template the sender does not have. */
export function useSmsTemplates() {
  return useQuery({
    queryKey: qk.smsTemplates(),
    queryFn: getSmsTemplates,
    staleTime: 30 * 60 * 1000,
  });
}

export function useRetrySms() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retrySms(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.sms });
      void qc.invalidateQueries({ queryKey: qk.lookup });
    },
  });
}
