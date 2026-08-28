/**
 * The queue is where a sale lives between the counter and the server, so these
 * tests are about the three things the product-dropdown change could break in
 * it, all of which cost a shop real money:
 *
 *   1. the body it sends must carry the product, because that is now the only
 *      thing that says what was sold and what it is worth;
 *   2. a refused duplicate invoice must come back naming the invoice number —
 *      the invoice IS the anti-double-payment rule now, and "already registered"
 *      without a number is unactionable at a counter;
 *   3. a sale queued by the version that scanned labels must not be retried
 *      forever against a server that can never accept it.
 */
import type { RegisterBody } from '../api/types';

jest.mock('@react-native-async-storage/async-storage', () =>
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

jest.mock('expo-crypto', () => {
  let n = 0;
  return { randomUUID: () => `key-${++n}` };
});

jest.mock('../api/client', () => ({
  hasTokens: () => true,
  // The real one is an instanceof check against ApiRequestError. Matching on
  // shape keeps this test off axios and expo-constants without changing what
  // the queue branches on.
  isApiError: (error: unknown) =>
    typeof error === 'object' && error !== null && 'code' in error && 'status' in error,
}));

jest.mock('../api/registrations', () => ({ createRegistration: jest.fn() }));

jest.mock('./net', () => ({ subscribeToConnectivity: () => () => undefined }));

/**
 * The queue keeps its items in module state, so every test needs a fresh copy of
 * the module — and `jest.resetModules()` re-runs the mock factories too, which
 * means the mocks have to be picked up AFTER the reset. Holding them from before
 * it leaves the test asserting against a different object than the queue used.
 */
let createRegistration: jest.Mock;

/** Must match queue.ts. Not exported there — it is an implementation detail
 *  everywhere except here, where the point is to write what an OLD app wrote. */
const STORAGE_KEY = 'dr_registration_queue_v1';

const BODY: RegisterBody = {
  product_id: 'p-ortho-60',
  customer_name: 'Asha Rao',
  customer_phone: '+919876543210',
  invoice_ref: 'INV-2043',
  invoice_date: null,
  customer_address: null,
};

function apiError(code: string, message: string, status: number | null) {
  return { code, message, status, isNetworkFailure: status === null, retryAfterMs: null };
}

/** Let the drain's promise chain — disk write, request, state commit — settle. */
async function settle(): Promise<void> {
  for (let i = 0; i < 6; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
}

type QueueModule = typeof import('./queue');

/** A queue with nothing but `stored` on disk, loaded and ready to drain. */
async function freshQueue(stored?: unknown[]): Promise<QueueModule> {
  jest.resetModules();

  // The shipped mock sets `module.exports = asMock`, so the module IS the store.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const storage = require('@react-native-async-storage/async-storage') as {
    setItem: (key: string, value: string) => Promise<void>;
  };
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  createRegistration = (require('../api/registrations') as { createRegistration: jest.Mock })
    .createRegistration;

  if (stored) await storage.setItem(STORAGE_KEY, JSON.stringify(stored));

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const queue = require('./queue') as QueueModule;
  await queue.loadQueue();
  return queue;
}

describe('what the queue sends', () => {
  it('sends the product the dealer picked, and no serial', async () => {
    const queue = await freshQueue();
    createRegistration.mockResolvedValue({ warranty: { id: 'w1' } });

    queue.enqueue(BODY);
    await settle();

    expect(createRegistration).toHaveBeenCalledTimes(1);
    const [sent, key] = createRegistration.mock.calls[0] as [RegisterBody, string];
    expect(sent.product_id).toBe('p-ortho-60');
    // The serial is gone from the wire, not merely unset: a stray key here would
    // be silently rejected by the server's schema.
    expect(sent).not.toHaveProperty('serial');
    // The idempotency key is the queue id — reused on every retry, forever.
    expect(key).toBe(queue.getSnapshot().items[0]?.id);
  });
});

describe('a duplicate invoice', () => {
  /** The server's own 409, whose wording cannot name the number. */
  const refuse = () =>
    createRegistration.mockRejectedValue(
      apiError(
        'duplicate_invoice',
        'This invoice number is already registered. Each sale needs its own invoice.',
        409
      )
    );

  it('fails the sale instead of retrying a request that can never succeed', async () => {
    const queue = await freshQueue();
    refuse();

    queue.enqueue(BODY);
    await settle();

    const item = queue.getSnapshot().items[0];
    expect(item?.status).toBe('failed');
    expect(item?.lastErrorCode).toBe('duplicate_invoice');
    expect(createRegistration).toHaveBeenCalledTimes(1);
    expect(queue.getSnapshot().failedCount).toBe(1);
  });

  it('names the invoice number, because that is the whole answer', async () => {
    const queue = await freshQueue();
    refuse();

    queue.enqueue(BODY);
    await settle();

    // Without the number this reads as "something is wrong". With it, the dealer
    // knows which bill of theirs the sale collided with.
    expect(queue.getSnapshot().items[0]?.lastError).toContain('INV-2043');
  });
});

describe('a sale queued before the dropdown replaced the scanner', () => {
  /** Exactly what the previous version wrote to disk: a serial, no product. */
  const legacy = {
    id: 'legacy-1',
    dealerId: null,
    createdAt: Date.now(),
    body: {
      serial: '7f3c9a2e-4b81-4a2a-9d0e-2f1b6c8a4d55',
      customer_name: 'Asha Rao',
      customer_phone: '+919876543210',
      invoice_ref: 'INV-1999',
    },
    status: 'pending',
    attempts: 0,
    nextAttemptAt: 0,
    lastError: null,
    lastErrorCode: null,
    resolution: null,
    result: null,
  };

  it('is failed with something the dealer can act on, not sent', async () => {
    const queue = await freshQueue([legacy]);

    const item = queue.getSnapshot().items[0];
    expect(item?.status).toBe('failed');
    expect(item?.lastErrorCode).toBe('missing_product');
    expect(item?.lastError).toContain('product');

    await settle();
    // The server would answer 422 to this body every time until the end of the
    // backoff ladder. Asking once is once too often.
    expect(createRegistration).not.toHaveBeenCalled();
  });

  it('keeps everything the dealer already typed, so the fix is one field', async () => {
    const queue = await freshQueue([legacy]);

    const item = queue.getSnapshot().items[0];
    expect(item?.body.customer_name).toBe('Asha Rao');
    expect(item?.body.invoice_ref).toBe('INV-1999');
  });

  it('leaves a sale that already landed alone', async () => {
    const queue = await freshQueue([{ ...legacy, status: 'done', resolution: 'registered' }]);

    // It was accepted under the old contract. There is nothing left to send and
    // nothing for the dealer to fix, so re-failing it would only raise an alarm.
    expect(queue.getSnapshot().items[0]?.status).toBe('done');
    expect(queue.getSnapshot().failedCount).toBe(0);
  });
});
