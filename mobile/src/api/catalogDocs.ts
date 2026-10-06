import { Directory, File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';

import { API_BASE_URL, API_PREFIX } from '../config';
import { api, getAccessToken } from './client';

/** One of the catalogue sheets the server renders on demand. */
export interface CatalogDoc {
  slug: string;
  title: string;
  subtitle: string;
}

export async function listCatalogDocs(): Promise<CatalogDoc[]> {
  const resp = await api.get<CatalogDoc[]>('/catalog/docs');
  return resp.data;
}

/**
 * Where downloaded sheets live: the cache directory, not documents.
 *
 * Each one is a snapshot of back-office data that can change at any time, so it
 * is never the authority — re-downloading is always correct, and letting Android
 * reclaim the space when storage runs low costs nothing.
 */
const DOCS_DIR = new Directory(Paths.cache, 'catalog');

/**
 * Fetch one catalogue sheet and hand it to whatever PDF viewer the phone has.
 *
 * It goes through the native downloader rather than axios because the file has to
 * land on disk for another app to open; that means passing the bearer token as a
 * header ourselves instead of relying on the axios interceptor.
 */
export async function openCatalogDoc(doc: CatalogDoc): Promise<void> {
  const token = getAccessToken();
  if (!token) throw new Error('not signed in');

  if (!DOCS_DIR.exists) DOCS_DIR.create({ intermediates: true });
  const target = new File(DOCS_DIR, `${doc.slug}.pdf`);

  const file = await File.downloadFileAsync(
    `${API_BASE_URL}${API_PREFIX}/catalog/docs/${doc.slug}.pdf`,
    target,
    // Overwrite: the sheet on the server is the live one, and a stale copy from
    // an earlier open would quietly show out-of-date points.
    { idempotent: true, headers: { Authorization: `Bearer ${token}` } }
  );

  if (!(await Sharing.isAvailableAsync())) {
    throw new Error('no viewer');
  }
  await Sharing.shareAsync(file.uri, {
    mimeType: 'application/pdf',
    UTI: 'com.adobe.pdf',
    dialogTitle: doc.title,
  });
}
