/**
 * Connectivity, treated as a hint rather than a verdict.
 *
 * A shop-floor phone reports "connected" on a wifi network whose uplink is dead,
 * and reports "no internet" on a captive-portal network that actually works. So
 * nothing here ever blocks a submission: the queue always tries, and this module
 * only answers "is now a good moment to try again?" and drives the banner.
 */
import * as Network from 'expo-network';
import { useEffect, useState } from 'react';

let online = true;

function toOnline(state: Network.NetworkState): boolean {
  // isInternetReachable is undefined on some platforms/states; fall back to
  // isConnected rather than assuming the worst and showing a false alarm.
  if (state.isInternetReachable !== undefined) {
    return state.isInternetReachable && state.isConnected !== false;
  }
  return state.isConnected !== false;
}

export function isOnline(): boolean {
  return online;
}

/** Fires only on transitions, with the new state. */
export function subscribeToConnectivity(listener: (online: boolean) => void): () => void {
  void Network.getNetworkStateAsync()
    .then((state) => {
      const next = toOnline(state);
      if (next !== online) {
        online = next;
        listener(next);
      }
    })
    .catch(() => undefined);

  const subscription = Network.addNetworkStateListener((state) => {
    const next = toOnline(state);
    if (next === online) return;
    online = next;
    listener(next);
  });

  return () => subscription.remove();
}

export function useIsOnline(): boolean {
  const [value, setValue] = useState(online);
  useEffect(() => subscribeToConnectivity(setValue), []);
  return value;
}
