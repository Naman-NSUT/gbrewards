import { api } from './client';

export interface ProductPoints {
  id: string;
  name: string;
  points_value: number;
}

export interface Faq {
  id: string;
  question: string;
  answer: string;
  sort_order: number;
}

export interface ContentDoc {
  key: string;
  title: string;
  body: string;
}

export async function listProductPoints(): Promise<ProductPoints[]> {
  const resp = await api.get<ProductPoints[]>('/products');
  return resp.data;
}

export async function listFaqs(): Promise<Faq[]> {
  const resp = await api.get<Faq[]>('/faqs');
  return resp.data;
}

export async function getContent(key: string): Promise<ContentDoc> {
  const resp = await api.get<ContentDoc>(`/content/${key}`);
  return resp.data;
}
