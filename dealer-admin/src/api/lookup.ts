import { api } from './client';
import type { SerialLookup } from './types';

/**
 * One request, one complete answer. Support staff work this screen with a
 * customer on the phone; five round-trips means five chances to be slow.
 */
export async function lookupSerial(serial: string): Promise<SerialLookup> {
  // /dealer-admin/, not /admin/: the two programmes have separate registries
  // and separate audiences, and this panel holds a dealer_admin token. The
  // worker path does not exist on the API at all, so this screen 404'd on
  // every search a support agent ever ran.
  const resp = await api.get<SerialLookup>(
    `/dealer-admin/lookup/${encodeURIComponent(serial)}`,
  );
  return resp.data;
}
