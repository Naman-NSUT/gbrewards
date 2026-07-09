import Constants from 'expo-constants';

const extra = (Constants.expoConfig?.extra ?? {}) as {
  apiBaseUrl?: string;
};

export const API_BASE_URL = extra.apiBaseUrl ?? 'http://10.0.2.2:8088';
export const API_PREFIX = '/api/v1';
