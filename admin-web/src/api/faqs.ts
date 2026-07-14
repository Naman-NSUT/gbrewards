import { api } from './client';
import type { Faq, FaqInput } from './types';

export async function listFaqs(): Promise<Faq[]> {
  const resp = await api.get<Faq[]>('/admin/faqs');
  return resp.data;
}

export async function createFaq(input: FaqInput): Promise<Faq> {
  const resp = await api.post<Faq>('/admin/faqs', input);
  return resp.data;
}

export async function updateFaq(id: string, input: Partial<FaqInput>): Promise<Faq> {
  const resp = await api.patch<Faq>(`/admin/faqs/${id}`, input);
  return resp.data;
}

export async function deleteFaq(id: string): Promise<void> {
  await api.delete(`/admin/faqs/${id}`);
}
