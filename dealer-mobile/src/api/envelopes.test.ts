/**
 * These three endpoints return an envelope, not a bare array.
 *
 * They were all typed as arrays. That does not fail loudly anywhere — it hands
 * a plain object to a FlatList and to .map(), which took down the Rewards and
 * Points screens the moment either was opened. TypeScript could not catch it
 * because the response type is an assertion about JSON the compiler never sees.
 *
 * The payloads below are the real shapes, copied from the live OpenAPI schema.
 */

import { listLedger } from './points';
import { listRedemptions, listRewards } from './rewards';

jest.mock('./client', () => ({ api: { get: jest.fn() } }));

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { api } = require('./client') as { api: { get: jest.Mock } };

const REWARD = {
  id: 'r1',
  name: 'Cordless drill',
  description: null,
  points_cost: 500,
  image_url: null,
  in_stock: true,
  affordable: false,
  short_by: 120,
};

const REDEMPTION = {
  id: 'x1',
  reward_id: 'r1',
  reward_name: 'Cordless drill',
  points: 500,
  status: 'pending',
  note: null,
  created_at: '2026-08-20T10:00:00Z',
  processed_at: null,
};

const LEDGER_ENTRY = {
  id: 'l1',
  amount: 120,
  type: 'registration_credit',
  created_at: '2026-08-20T10:00:00Z',
};

beforeEach(() => api.get.mockReset());

describe('responses that arrive wrapped in an envelope', () => {
  it('unwraps the rewards catalogue and keeps the balance it was priced against', async () => {
    api.get.mockResolvedValue({
      data: { balance: 380, pending: 0, available: 380, items: [REWARD] },
    });

    const catalogue = await listRewards();

    // An array here, not the envelope: the screen feeds `items` to a FlatList.
    expect(Array.isArray(catalogue.items)).toBe(true);
    expect(catalogue.items).toHaveLength(1);
    // The balance travels with the catalogue so affordability cannot disagree.
    expect(catalogue.available).toBe(380);
  });

  it('reads affordability from the server rather than recomputing it', async () => {
    api.get.mockResolvedValue({
      data: { balance: 500, pending: 500, available: 0, items: [REWARD] },
    });

    const { items } = await listRewards();

    // Balance covers the cost, but every point is held by a pending request.
    // A client comparing balance to cost would offer a button the server refuses.
    expect(items[0]?.affordable).toBe(false);
    expect(items[0]?.short_by).toBe(120);
  });

  it('unwraps the redemptions page into an array', async () => {
    api.get.mockResolvedValue({
      data: { total: 1, limit: 50, offset: 0, items: [REDEMPTION] },
    });

    const rows = await listRedemptions();

    expect(Array.isArray(rows)).toBe(true);
    expect(rows[0]?.id).toBe('x1');
  });

  it('unwraps the ledger page into an array', async () => {
    api.get.mockResolvedValue({
      data: { total: 1, limit: 50, offset: 0, balance: 120, items: [LEDGER_ENTRY] },
    });

    const rows = await listLedger();

    expect(Array.isArray(rows)).toBe(true);
    expect(rows[0]?.amount).toBe(120);
  });

  it('never hands a bare envelope to a list', async () => {
    // The regression itself: returning resp.data would return an object, and
    // `Array.isArray` on it is false — which is precisely what a FlatList chokes on.
    api.get.mockResolvedValue({ data: { total: 0, limit: 50, offset: 0, items: [] } });
    expect(Array.isArray(await listRedemptions())).toBe(true);

    api.get.mockResolvedValue({ data: { total: 0, limit: 50, offset: 0, balance: 0, items: [] } });
    expect(Array.isArray(await listLedger())).toBe(true);
  });
});
