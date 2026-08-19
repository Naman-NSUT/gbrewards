import { useEffect, useSyncExternalStore } from 'react';

import {
  getItem,
  getSnapshot,
  loadQueue,
  startQueue,
  subscribe,
  type QueuedRegistration,
  type QueueSnapshot,
} from './queue';

export function useQueue(): QueueSnapshot {
  return useSyncExternalStore(subscribe, getSnapshot);
}

/**
 * Follow one submission. Survives pruning — see the resolved archive in
 * queue.ts — so a confirmation screen left open on the counter never blanks out.
 */
export function useQueueItem(id: string): QueuedRegistration | null {
  return useSyncExternalStore(subscribe, () => getItem(id));
}

/** Mounted once, at the root: loads the queue from disk and starts draining. */
export function useQueueRuntime(): void {
  useEffect(() => {
    void loadQueue();
    return startQueue();
  }, []);
}
