import { Directory, File, Paths } from 'expo-file-system';
import { getContentUriAsync } from 'expo-file-system/legacy';
import * as IntentLauncher from 'expo-intent-launcher';
import * as Sharing from 'expo-sharing';
import { Platform } from 'react-native';

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

/** Grants the receiving app read access to the one file we hand it. */
const FLAG_GRANT_READ_URI_PERMISSION = 1;

/**
 * Open a downloaded sheet in the phone's PDF viewer.
 *
 * ACTION_VIEW rather than a share sheet: tapping a document should show the
 * document. Sharing it was the wrong verb — it put a "Share with…" chooser
 * between the worker and the thing they asked to read.
 *
 * Android will not accept a `file://` URI across an app boundary (it throws
 * FileUriExposedException), so the file is handed over as a `content://` URI
 * from our own FileProvider, with read permission granted for that URI alone.
 */
async function viewPdf(uri: string, title: string): Promise<void> {
  if (Platform.OS !== 'android') {
    // iOS has no equivalent intent; its share sheet is the system's own
    // "open in" affordance and previews the PDF directly.
    await Sharing.shareAsync(uri, { UTI: 'com.adobe.pdf', dialogTitle: title });
    return;
  }

  const contentUri = await getContentUriAsync(uri);
  try {
    await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
      data: contentUri,
      type: 'application/pdf',
      flags: FLAG_GRANT_READ_URI_PERMISSION,
    });
  } catch {
    // No PDF viewer installed — a real possibility on a bare handset. The share
    // sheet at least offers the apps that can take the file (Drive, Files, a
    // browser, WhatsApp), which beats a dead end.
    if (!(await Sharing.isAvailableAsync())) throw new Error('no viewer');
    await Sharing.shareAsync(uri, { mimeType: 'application/pdf', dialogTitle: title });
  }
}

/**
 * Fetch one catalogue sheet and open it.
 *
 * It goes through the native downloader rather than axios because the file has to
 * land on disk for another app to read; that means passing the bearer token as a
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

  await viewPdf(file.uri, doc.title);
}
