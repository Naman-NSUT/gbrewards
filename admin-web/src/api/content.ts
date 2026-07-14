import { api } from './client';
import type { ContentDoc, ContentDocInput } from './types';

export async function listContentDocs(): Promise<ContentDoc[]> {
  const resp = await api.get<ContentDoc[]>('/admin/content');
  return resp.data;
}

export async function getContentDoc(key: string): Promise<ContentDoc> {
  const resp = await api.get<ContentDoc>(`/admin/content/${key}`);
  return resp.data;
}

export async function upsertContentDoc(key: string, input: ContentDocInput): Promise<ContentDoc> {
  const resp = await api.put<ContentDoc>(`/admin/content/${key}`, input);
  return resp.data;
}
