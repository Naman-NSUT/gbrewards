import { ConfigContext, ExpoConfig } from 'expo/config';

// API base URL per environment. Override with API_BASE_URL env at start time, e.g.
//   API_BASE_URL=http://192.168.1.20:8000 npx expo start
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'GB Rewards',
  slug: 'scanrewards',
  scheme: 'scanrewards',
  extra: {
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://localhost:8000',
    sentryDsn: process.env.SENTRY_DSN ?? '',
  },
  plugins: [
    [
      'expo-camera',
      {
        cameraPermission: 'GB Rewards uses the camera to scan product QR codes.',
      },
    ],
    'expo-secure-store',
    '@sentry/react-native',
  ],
});
