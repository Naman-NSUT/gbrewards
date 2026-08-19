import Constants from 'expo-constants';

const extra = (Constants.expoConfig?.extra ?? {}) as {
  apiBaseUrl?: string;
};

export const API_BASE_URL = extra.apiBaseUrl ?? 'http://10.0.2.2:8000';
export const API_PREFIX = '/api/v1';

// A dealer is at a counter with a customer waiting. Twenty seconds is already
// past the point where they will assume it failed; beyond that the offline
// queue is a better answer than a longer spinner.
export const REQUEST_TIMEOUT_MS = 20_000;
