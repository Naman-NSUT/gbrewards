import { api } from './client';
import type { Page, SmsRow, SmsStatus, SmsTemplates } from './types';

export interface SmsQuery {
  status?: SmsStatus;
  phone?: string;
  template_key?: string;
  warranty_id?: string;
  q?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listSms(params: SmsQuery): Promise<Page<SmsRow>> {
  const resp = await api.get<Page<SmsRow>>('/dealer-admin/sms', { params });
  return resp.data;
}

/** The template registry, keyed by template_key — the filter's options. */
export async function getSmsTemplates(): Promise<SmsTemplates> {
  const resp = await api.get<SmsTemplates>('/dealer-admin/sms/templates');
  return resp.data;
}

export async function getSms(id: string): Promise<SmsRow> {
  const resp = await api.get<SmsRow>(`/dealer-admin/sms/${id}`);
  return resp.data;
}

/** Re-sends the same template + variables and increments `attempts` on the row. */
export async function retrySms(id: string): Promise<SmsRow> {
  const resp = await api.post<SmsRow>(`/dealer-admin/sms/${id}/retry`);
  return resp.data;
}
