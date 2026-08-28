/**
 * The product catalogue the dealer picks from when registering a sale.
 *
 * This list is now load-bearing in a way it never was while the app scanned
 * labels: the serial used to say what was sold, so the app never needed to know
 * what products existed. Now the dropdown is the ONLY thing that identifies the
 * mattress — and, through the product's point rate, what the sale is worth.
 *
 * Which is why the last good list is written to disk. A shop with no signal that
 * reopens the app would otherwise face an empty dropdown and be unable to
 * register anything, and the offline queue — the whole reason this app works
 * during an outage — would have nothing to queue. A catalogue that is a few days
 * stale still lets the sale be recorded; the server re-checks the product on
 * arrival and refuses anything that has since been withdrawn.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

import { api } from './client';
import type { DealerProduct } from './types';

const CACHE_KEY = 'dr_product_catalogue_v1';

async function readCache(): Promise<DealerProduct[]> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    return Array.isArray(parsed) ? (parsed as DealerProduct[]) : [];
  } catch {
    return [];
  }
}

/**
 * Active products, newest list first, falling back to the copy on this phone.
 *
 * The fallback is deliberately silent: a dealer at a counter cannot act on "the
 * catalogue is stale", and the alternative — an error where a working dropdown
 * would do — costs a sale. An empty cache still throws, because an empty
 * dropdown needs to say why.
 */
export async function listProducts(): Promise<DealerProduct[]> {
  try {
    const resp = await api.get<DealerProduct[]>('/dealer/products');
    // Write-through, and never awaited: the caller is waiting to render a
    // dropdown, not to finish a disk write.
    void AsyncStorage.setItem(CACHE_KEY, JSON.stringify(resp.data)).catch(() => {
      // The previous good copy stays on disk. The next successful fetch rewrites it.
    });
    return resp.data;
  } catch (error) {
    const cached = await readCache();
    if (cached.length > 0) return cached;
    throw error;
  }
}
