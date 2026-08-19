/**
 * The durable submission queue. This is the part of the app that makes the
 * product work on a shop floor.
 *
 * The rule everything here follows: THE SALE RECORD IS THE PRODUCT. A dealer who
 * taps submit has made a sale; the network is a detail. So the moment they tap:
 *
 *   1. a UUIDv4 idempotency key is minted and the exact request body is frozen,
 *   2. both are written to disk BEFORE any network call is attempted,
 *   3. the key is reused on every retry, forever, until the item resolves.
 *
 * That ordering is the whole design. If the app is killed between tap and
 * response — dropped phone, battery, OS reaping a backgrounded app — the item is
 * already on disk and replays with the same key, and the backend's idempotency
 * table returns the ORIGINAL result instead of creating a second warranty.
 *
 * Retry policy, keyed on what the failure actually means:
 *
 *   no response / 5xx / 429   → transient. Retry with backoff, forever.
 *   401                       → transient. The session expired; the item waits
 *                               for the dealer to sign in rather than dying.
 *   409 already_registered    → resolved, not failed. The unit IS registered.
 *   409 request_in_progress   → the first attempt is still running. Back off.
 *   409 idempotency_key_reused→ permanent. Only reachable via a client bug; a
 *                               changed body must get a NEW key (see `replace`).
 *   other 4xx                 → permanent. The dealer must fix something, so the
 *                               server's message is kept and shown verbatim.
 *
 * Nothing is ever dropped silently. Every item is in exactly one visible state.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { randomUUID } from 'expo-crypto';
import { AppState, type AppStateStatus } from 'react-native';

import { hasTokens, isApiError } from '../api/client';
import { createRegistration } from '../api/registrations';
import type { RegisterBody, RegisterOut } from '../api/types';
import { subscribeToConnectivity } from './net';

const STORAGE_KEY = 'dr_registration_queue_v1';

/** Resolved items linger briefly so the confirmation screen can show them. */
const DONE_RETENTION_MS = 5 * 60_000;

/** Backoff ladder, in ms, indexed by attempt count. Last value repeats. */
const BACKOFF_MS = [2_000, 5_000, 15_000, 45_000, 120_000, 300_000];

export type QueueItemStatus = 'pending' | 'sending' | 'failed' | 'done';

/** How a `done` item ended, because "done" alone would hide a real outcome. */
export type QueueResolution = 'registered' | 'already_registered';

export interface QueuedRegistration {
  /** The idempotency key. Minted once, reused on every retry forever. */
  id: string;
  /**
   * The dealership this sale was made under.
   *
   * Idempotency keys are scoped per dealer server-side, so replaying one shop's
   * queued sale while a different shop is signed in on the same phone would
   * create a real registration under the wrong dealership — and pay the wrong
   * shop. Such items wait for their own account instead.
   */
  dealerId: string | null;
  createdAt: number;
  /** Frozen at submit. Changing it requires a new key — see `replace`. */
  body: RegisterBody;
  status: QueueItemStatus;
  attempts: number;
  nextAttemptAt: number;
  lastError: string | null;
  lastErrorCode: string | null;
  resolution: QueueResolution | null;
  result: RegisterOut | null;
}

export interface QueueSnapshot {
  items: QueuedRegistration[];
  /** Sales made but not yet acknowledged by the server. The badge number. */
  pendingCount: number;
  /** Sales the server rejected. These need a human. */
  failedCount: number;
  /** A send is in flight right now. */
  syncing: boolean;
}

const EMPTY: QueueSnapshot = { items: [], pendingCount: 0, failedCount: 0, syncing: false };

let items: QueuedRegistration[] = [];
let activeDealerId: string | null = null;
let snapshot: QueueSnapshot = EMPTY;
let loaded = false;
let draining = false;
let drainTimer: ReturnType<typeof setTimeout> | null = null;
let started = false;

const listeners = new Set<() => void>();

/**
 * Resolved items that have aged out of the live queue.
 *
 * Kept so a confirmation screen still open on the counter — or reopened from a
 * navigation restore — can still show what happened to that sale, rather than
 * going blank on the one screen whose whole job is to say "this landed".
 */
const archive = new Map<string, QueuedRegistration>();
const ARCHIVE_LIMIT = 30;

// All writes go through one promise chain: two concurrent mutations must not
// both read the stored array and write back divergent copies.
let writeChain: Promise<void> = Promise.resolve();

function persist(): Promise<void> {
  const payload = JSON.stringify(items);
  writeChain = writeChain
    .then(() => AsyncStorage.setItem(STORAGE_KEY, payload))
    .catch(() => {
      // A failed write leaves the previous good copy on disk. Losing the newest
      // item is bad, but the in-memory copy still drives this session's UI and
      // the next mutation rewrites the whole array.
    });
  return writeChain;
}

function rebuildSnapshot(): void {
  let pendingCount = 0;
  let failedCount = 0;
  let syncing = false;
  for (const item of items) {
    if (item.status === 'pending') pendingCount += 1;
    if (item.status === 'sending') {
      pendingCount += 1;
      syncing = true;
    }
    if (item.status === 'failed') failedCount += 1;
  }
  snapshot = { items, pendingCount, failedCount, syncing };
}

function emit(): void {
  rebuildSnapshot();
  for (const listener of listeners) listener();
}

/** Mutate + persist + notify. Every state change in this module goes through it. */
function commit(next: QueuedRegistration[]): void {
  items = next;
  void persist();
  emit();
  scheduleDrain();
}

function backoffFor(attempts: number): number {
  const base = BACKOFF_MS[Math.min(attempts, BACKOFF_MS.length - 1)] ?? 300_000;
  // Jitter so a shop with several devices coming back online together does not
  // hit the backend in lockstep.
  return Math.round(base * (0.8 + Math.random() * 0.4));
}

function prune(list: QueuedRegistration[]): QueuedRegistration[] {
  const cutoff = Date.now() - DONE_RETENTION_MS;
  const kept: QueuedRegistration[] = [];
  for (const item of list) {
    if (item.status === 'done' && item.createdAt <= cutoff) {
      archive.set(item.id, item);
      continue;
    }
    kept.push(item);
  }
  while (archive.size > ARCHIVE_LIMIT) {
    const oldest = archive.keys().next();
    if (oldest.done) break;
    archive.delete(oldest.value);
  }
  return kept;
}

let loading: Promise<void> | null = null;

export function loadQueue(): Promise<void> {
  if (loaded) return Promise.resolve();
  loading = loading ?? readFromDisk();
  return loading;
}

async function readFromDisk(): Promise<void> {
  let stored: QueuedRegistration[] = [];
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    stored = raw ? (JSON.parse(raw) as QueuedRegistration[]) : [];
  } catch {
    stored = [];
  }

  // Anything enqueued while this read was in flight wins — dropping it to honour
  // the disk would lose the newest sale, which is the one thing this module
  // exists to prevent.
  const inMemory = new Set(items.map((item) => item.id));
  const restored = stored
    .filter((item) => !inMemory.has(item.id))
    .map((item) => ({
      ...item,
      dealerId: item.dealerId ?? null,
      // An item stuck in `sending` means the app died mid-request. Retrying is
      // safe precisely because the key is stable: a landed request replays its
      // original response instead of creating a second warranty.
      status: item.status === 'sending' ? ('pending' as const) : item.status,
    }));

  loaded = true;
  items = prune([...items, ...restored]);
  void persist();
  emit();
  scheduleDrain();
}

/** Told by AuthContext who is signed in. Null when signed out. */
export function setActiveDealer(dealerId: string | null): void {
  activeDealerId = dealerId;
  if (dealerId) void drain();
}

/** True when this item belongs to a dealership that is not currently signed in. */
export function isForeignItem(item: QueuedRegistration): boolean {
  return (
    item.dealerId !== null && activeDealerId !== null && item.dealerId !== activeDealerId
  );
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getSnapshot(): QueueSnapshot {
  return snapshot;
}

export function getItem(id: string): QueuedRegistration | null {
  return items.find((item) => item.id === id) ?? archive.get(id) ?? null;
}

/**
 * Record a sale. Returns the queue id (which IS the idempotency key) so the
 * confirmation screen can follow this specific submission.
 */
export function enqueue(body: RegisterBody): string {
  const item: QueuedRegistration = {
    id: randomUUID(),
    dealerId: activeDealerId,
    createdAt: Date.now(),
    body,
    status: 'pending',
    attempts: 0,
    nextAttemptAt: 0,
    lastError: null,
    lastErrorCode: null,
    resolution: null,
    result: null,
  };
  commit([item, ...items]);
  void drain();
  return item.id;
}

/** Retry a failed item unchanged — same key, because it is the same sale. */
export function retry(id: string): void {
  commit(
    items.map((item) =>
      item.id === id && item.status === 'failed'
        ? { ...item, status: 'pending' as const, nextAttemptAt: 0, lastError: null }
        : item
    )
  );
  void drain();
}

/**
 * Resubmit with corrected details.
 *
 * A new key is minted deliberately. The backend rejects the same key carrying a
 * different body with 409 `idempotency_key_reused` — and it is right to: that is
 * not a retry, and replaying the first answer would attach one customer's
 * details to another's warranty.
 */
export function replace(id: string, body: RegisterBody): string {
  const next: QueuedRegistration = {
    id: randomUUID(),
    dealerId: activeDealerId,
    createdAt: Date.now(),
    body,
    status: 'pending',
    attempts: 0,
    nextAttemptAt: 0,
    lastError: null,
    lastErrorCode: null,
    resolution: null,
    result: null,
  };
  commit([next, ...items.filter((item) => item.id !== id)]);
  void drain();
  return next.id;
}

/** Remove an item the dealer has seen and acknowledged. Never called silently. */
export function dismiss(id: string): void {
  commit(items.filter((item) => item.id !== id));
}

function update(id: string, patch: Partial<QueuedRegistration>): void {
  commit(items.map((item) => (item.id === id ? { ...item, ...patch } : item)));
}

function due(item: QueuedRegistration, now: number): boolean {
  if (isForeignItem(item)) return false;
  return item.status === 'pending' && item.nextAttemptAt <= now;
}

/**
 * Send everything that is due, oldest first.
 *
 * Sequential on purpose: the dealer's own sales are ordered, the payloads are
 * tiny, and a serial burst is far kinder to a weak connection than a parallel
 * one that times out in five places at once.
 */
export async function drain(): Promise<void> {
  if (draining) return;
  // Claimed before the first await: two callers must not both enter the loop and
  // race each other onto the same item.
  draining = true;
  try {
    if (!loaded) await loadQueue();
    // Signed out: items wait rather than 401 themselves to death.
    if (!hasTokens()) return;

    for (;;) {
      const now = Date.now();
      const next = [...items].reverse().find((item) => due(item, now));
      if (!next) break;

      update(next.id, { status: 'sending' });
      try {
        const result = await createRegistration(next.body, next.id);
        update(next.id, {
          status: 'done',
          result,
          resolution: 'registered',
          lastError: null,
          lastErrorCode: null,
          attempts: next.attempts + 1,
        });
      } catch (error) {
        update(next.id, classify(next, error));
        // A connection-level, throttling or server failure applies to every
        // queued item, so end the pass rather than burning a 20-second timeout
        // per sale. An item-specific wait only holds up that one item, and the
        // loop moves on because its next attempt has been pushed forward.
        const global =
          !isApiError(error) ||
          error.isNetworkFailure ||
          error.status === 429 ||
          (error.status ?? 0) >= 500;
        if (global) break;
      }
    }
  } finally {
    draining = false;
    scheduleDrain();
  }
}

function classify(item: QueuedRegistration, error: unknown): Partial<QueuedRegistration> {
  const attempts = item.attempts + 1;
  const retryLater = (message: string, code: string, delay?: number) => ({
    status: 'pending' as const,
    attempts,
    nextAttemptAt: Date.now() + (delay ?? backoffFor(attempts)),
    lastError: message,
    lastErrorCode: code,
  });

  if (!isApiError(error)) {
    return retryLater('Could not reach GoodBed. Will keep trying.', 'unknown_error');
  }

  if (error.isNetworkFailure) {
    return retryLater('Waiting for a connection.', error.code);
  }

  const status = error.status ?? 0;

  if (status === 401 || status === 403) {
    // 403 covers dealer_inactive / account_disabled, which a re-login resolves,
    // and not_your_unit / not_allocated, which it does not. Only the auth-shaped
    // ones are worth waiting on; the rest are a real refusal.
    if (error.code === 'invalid_token' || error.code === 'account_disabled') {
      return retryLater('Sign in again to send this sale.', error.code, 60_000);
    }
    if (error.code === 'dealer_inactive') {
      return retryLater('This dealership is not active. Contact GoodBed.', error.code, 300_000);
    }
    if (status === 401) {
      return retryLater('Sign in again to send this sale.', error.code, 60_000);
    }
  }

  if (status === 409) {
    if (error.code === 'already_registered') {
      // The sale exists in the system — just not under this submission. That is
      // an answer, not a failure, and the dealer needs to see it as such.
      return {
        status: 'done',
        attempts,
        resolution: 'already_registered',
        lastError: error.message,
        lastErrorCode: error.code,
      };
    }
    if (error.code === 'request_in_progress') {
      return retryLater('Finishing an earlier attempt…', error.code, 3_000);
    }
    return { status: 'failed', attempts, lastError: error.message, lastErrorCode: error.code };
  }

  if (status === 429) {
    return retryLater(
      'GoodBed is throttling registrations. Will retry.',
      error.code,
      error.retryAfterMs ?? backoffFor(attempts + 2)
    );
  }

  if (status >= 500) {
    return retryLater('GoodBed server error. Will retry.', error.code);
  }

  // Everything else is the dealer's to fix: a bad phone number, an unallocated
  // unit, a missing invoice. Keep the server's own words.
  return { status: 'failed', attempts, lastError: error.message, lastErrorCode: error.code };
}

function scheduleDrain(): void {
  if (drainTimer) {
    clearTimeout(drainTimer);
    drainTimer = null;
  }
  const waiting = items.filter((item) => item.status === 'pending' && !isForeignItem(item));
  if (waiting.length === 0) return;
  const now = Date.now();
  const earliest = Math.min(...waiting.map((item) => item.nextAttemptAt));
  const delay = Math.max(500, earliest - now);
  drainTimer = setTimeout(() => {
    drainTimer = null;
    void drain();
  }, delay);
}

/**
 * Wire the queue to the two events that mean "the network might be back":
 * the app coming to the foreground, and connectivity being regained.
 */
export function startQueue(): () => void {
  if (started) return () => undefined;
  started = true;

  void loadQueue().then(() => drain());

  const appStateSub = AppState.addEventListener('change', (state: AppStateStatus) => {
    if (state === 'active') void drain();
  });
  const netUnsub = subscribeToConnectivity((online) => {
    if (online) void drain();
  });

  return () => {
    started = false;
    appStateSub.remove();
    netUnsub();
    if (drainTimer) clearTimeout(drainTimer);
    drainTimer = null;
  };
}
