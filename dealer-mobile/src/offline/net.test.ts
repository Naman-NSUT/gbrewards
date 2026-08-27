import type { NetworkState } from 'expo-network';

/**
 * These tests exist because of one specific shop-floor failure.
 *
 * Three things subscribe to connectivity at once — the queue's drain, the
 * offline banner, the confirmation screen. When the wifi comes back, all three
 * must hear about it. The old implementation compared the incoming state against
 * a shared flag inside EACH subscriber's own callback, so the first callback to
 * run flipped the flag and the rest saw "no change": the banner cleared and the
 * queue never drained, leaving a shop's sales unsent until an app refocus or a
 * backoff timer happened to fire.
 *
 * So every test here registers MORE THAN ONE subscriber and asserts what each of
 * them was told. A single-subscriber test would pass against the broken code.
 */

const mockAddNetworkStateListener = jest.fn();
const mockGetNetworkStateAsync = jest.fn();

jest.mock('expo-network', () => ({
  addNetworkStateListener: mockAddNetworkStateListener,
  getNetworkStateAsync: mockGetNetworkStateAsync,
}));

const ONLINE: NetworkState = { isConnected: true, isInternetReachable: true };
const OFFLINE: NetworkState = { isConnected: false, isInternetReachable: false };

type NetModule = typeof import('./net');

/** Platform callbacks registered this test, so we can count and drive them. */
let platformCallbacks: ((state: NetworkState) => void)[] = [];
let net: NetModule;

/** Let the startup probe's promise chain settle. */
const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

/** Deliver one platform event to every listener expo-network handed out. */
function emit(state: NetworkState): void {
  for (const callback of platformCallbacks) callback(state);
}

function loadNet(probeResult: NetworkState): NetModule {
  mockGetNetworkStateAsync.mockResolvedValue(probeResult);
  // Fresh module registry per test: `online`, the subscriber Set and the
  // installed platform listener are module-level and would otherwise leak.
  jest.resetModules();
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require('./net') as NetModule;
}

beforeEach(() => {
  platformCallbacks = [];
  mockAddNetworkStateListener.mockReset();
  mockGetNetworkStateAsync.mockReset();
  mockAddNetworkStateListener.mockImplementation((callback: (state: NetworkState) => void) => {
    platformCallbacks.push(callback);
    return { remove: jest.fn() };
  });
  // The module starts optimistic (online = true); probing "online" keeps the
  // launch quiet so each test drives the transition it actually cares about.
  net = loadNet(ONLINE);
});

describe('subscribeToConnectivity', () => {
  it('tells EVERY subscriber about one transition, exactly once', async () => {
    const queue = jest.fn();
    const banner = jest.fn();
    const confirmation = jest.fn();
    net.subscribeToConnectivity(queue);
    net.subscribeToConnectivity(banner);
    net.subscribeToConnectivity(confirmation);
    await flush();

    emit(OFFLINE);

    // The bug: whichever callback ran first flipped the shared flag, so the
    // other two were told nothing and the queue never drained.
    expect(queue).toHaveBeenCalledTimes(1);
    expect(queue).toHaveBeenCalledWith(false);
    expect(banner).toHaveBeenCalledTimes(1);
    expect(banner).toHaveBeenCalledWith(false);
    expect(confirmation).toHaveBeenCalledTimes(1);
    expect(confirmation).toHaveBeenCalledWith(false);
    expect(net.isOnline()).toBe(false);
  });

  it('reports the opening state to everyone already listening', async () => {
    // An app launched with the radio already off: one probe, not one per
    // subscriber, and its answer reaches all of them rather than whichever
    // subscriber's own probe happened to resolve first.
    net = loadNet(OFFLINE);
    const queue = jest.fn();
    const banner = jest.fn();
    const confirmation = jest.fn();
    net.subscribeToConnectivity(queue);
    net.subscribeToConnectivity(banner);
    net.subscribeToConnectivity(confirmation);

    await flush();

    expect(queue).toHaveBeenCalledWith(false);
    expect(banner).toHaveBeenCalledWith(false);
    expect(confirmation).toHaveBeenCalledWith(false);
    expect(net.isOnline()).toBe(false);
  });

  it('stays quiet when the platform repeats a state nobody transitioned to', async () => {
    const queue = jest.fn();
    const banner = jest.fn();
    net.subscribeToConnectivity(queue);
    net.subscribeToConnectivity(banner);
    await flush();

    emit(OFFLINE);
    emit(OFFLINE);
    emit(OFFLINE);

    // Android re-emits the same state on unrelated network changes; a drain per
    // event would hammer the API from every phone on a flaky shop wifi.
    expect(queue).toHaveBeenCalledTimes(1);
    expect(banner).toHaveBeenCalledTimes(1);
  });

  it('keeps delivering to the rest after one subscriber unsubscribes', async () => {
    const queue = jest.fn();
    const banner = jest.fn();
    const confirmation = jest.fn();
    net.subscribeToConnectivity(queue);
    net.subscribeToConnectivity(banner);
    const unsubscribe = net.subscribeToConnectivity(confirmation);
    await flush();

    unsubscribe();
    emit(OFFLINE);

    expect(confirmation).not.toHaveBeenCalled();
    expect(queue).toHaveBeenCalledWith(false);
    expect(banner).toHaveBeenCalledWith(false);
  });

  it('does not skip a neighbour when a subscriber unsubscribes inside its own callback', async () => {
    // The confirmation screen navigates away on reconnect, which unmounts it and
    // unsubscribes mid-notification. Deleting from the Set being iterated would
    // skip whoever came next — and the queue's drain is a plausible "next".
    const confirmation = jest.fn(() => unsubscribeConfirmation());
    const unsubscribeConfirmation = net.subscribeToConnectivity(confirmation);
    const queue = jest.fn();
    net.subscribeToConnectivity(queue);
    await flush();

    emit(OFFLINE);

    expect(confirmation).toHaveBeenCalledTimes(1);
    expect(queue).toHaveBeenCalledTimes(1);
  });

  it('installs exactly one platform listener however many subscribers there are', async () => {
    net.subscribeToConnectivity(jest.fn());
    net.subscribeToConnectivity(jest.fn());
    net.subscribeToConnectivity(jest.fn());
    net.subscribeToConnectivity(jest.fn());
    await flush();

    // One native listener and one startup probe for the whole app: a fourth
    // subscriber must not be able to change how anything is delivered.
    expect(mockAddNetworkStateListener).toHaveBeenCalledTimes(1);
    expect(mockGetNetworkStateAsync).toHaveBeenCalledTimes(1);
  });
});
