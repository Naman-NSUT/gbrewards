/**
 * Connectivity, treated as a hint rather than a verdict.
 *
 * A shop-floor phone reports "connected" on a wifi network whose uplink is dead,
 * and reports "no internet" on a captive-portal network that actually works. So
 * nothing here ever blocks a submission: the queue always tries, and this module
 * only answers "is now a good moment to try again?" and drives the banner.
 *
 * Shape of this module, and why it is not one listener per subscriber:
 *
 * Three things subscribe concurrently — the queue's drain-on-reconnect, the
 * offline banner, and the confirmation screen. If each of them installed its own
 * platform listener and each compared the incoming state against a shared
 * `online` flag, the first callback to run would flip the flag and every other
 * callback would then see "no change" and stay silent. The banner would win that
 * race and the queue would never drain, so a shop's queued sales would sit unsent
 * — on the one code path this whole offline design exists for. A dealer's
 * customer's 5-year warranty goes unregistered and the dealer is not paid.
 *
 * So: ONE platform listener, fanned out to a Set of subscribers, with the
 * transition detected once in apply() BEFORE anyone is notified. Per-subscriber
 * transition flags would fix the fan-out but leave each subscriber with its own
 * idea of "current", so isOnline() could disagree with what a subscriber was last
 * told, and every new subscriber would still add another native listener plus
 * another redundant startup probe. Centralising the comparison makes the failure
 * structurally impossible: adding a fourth subscriber cannot change delivery,
 * because no subscriber takes any part in detecting the transition.
 */
import * as Network from 'expo-network';
import { useSyncExternalStore } from 'react';

type ConnectivityListener = (online: boolean) => void;

let online = true;

const subscribers = new Set<ConnectivityListener>();

let platformSubscription: ReturnType<typeof Network.addNetworkStateListener> | null = null;

function toOnline(state: Network.NetworkState): boolean {
  // isInternetReachable is undefined on some platforms/states; fall back to
  // isConnected rather than assuming the worst and showing a false alarm.
  if (state.isInternetReachable !== undefined) {
    return state.isInternetReachable && state.isConnected !== false;
  }
  return state.isConnected !== false;
}

/**
 * The single point where a transition is decided. Everything else in this module
 * routes through here, so `online` and what subscribers were last told can never
 * drift apart.
 */
function apply(state: Network.NetworkState): void {
  const next = toOnline(state);
  if (next === online) return;
  online = next;
  // Iterate a COPY: the confirmation screen unsubscribes from inside its own
  // callback when a reconnect navigates it away, and deleting from the live Set
  // mid-iteration would skip whichever subscriber happened to come next — the
  // queue's drain among them.
  for (const listener of [...subscribers]) listener(next);
}

/**
 * Installed on the first subscriber and kept for the module's lifetime.
 *
 * Tearing it down when the last subscriber leaves would freeze `online` at
 * whatever it was, and a reconnect arriving before the next subscribe would be
 * missed entirely — isOnline() would then answer with a stale flag and the queue
 * would wait for a backoff timer instead of draining.
 */
function ensurePlatformListener(): void {
  if (platformSubscription) return;
  platformSubscription = Network.addNetworkStateListener(apply);
  // One startup probe, not one per subscriber: an app launched with the radio
  // already off must tell EVERYONE already listening, not whichever subscriber's
  // probe happened to resolve first. Later subscribers need no probe of their
  // own — by then `online` is already current and isOnline() answers for them.
  void Network.getNetworkStateAsync().then(apply).catch(() => undefined);
}

export function isOnline(): boolean {
  return online;
}

/** Fires only on transitions, with the new state. */
export function subscribeToConnectivity(listener: ConnectivityListener): () => void {
  subscribers.add(listener);
  ensurePlatformListener();
  return () => {
    subscribers.delete(listener);
  };
}

/**
 * useSyncExternalStore, not useState + useEffect: the old form captured `online`
 * at first render and only subscribed on commit, so a transition landing in that
 * gap was never delivered and left the banner permanently stale.
 */
export function useIsOnline(): boolean {
  return useSyncExternalStore(subscribeToConnectivity, isOnline);
}
