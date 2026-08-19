import { api } from './client';
import type { SerialLookup } from './types';

/**
 * One request, one complete answer. Support staff work this screen with a
 * customer on the phone; five round-trips means five chances to be slow.
 */
export async function lookupSerial(serial: string): Promise<SerialLookup> {
  const resp = await api.get<SerialLookup>(`/admin/lookup/${encodeURIComponent(serial)}`);
  return resp.data;
}
