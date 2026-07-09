import { ConfigContext, ExpoConfig } from 'expo/config';

// API base URL per environment. Override with API_BASE_URL env at start time, e.g.
//   API_BASE_URL=http://192.168.1.20:8000 npx expo start
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'GB Rewards',
  slug: 'scanrewards',
  scheme: 'scanrewards',
  owner: 'naman04',
  android: {
    ...config.android,
    package: 'in.gbrewards.gbrewards',
  },
  extra: {
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://10.0.2.2:8088',
    sentryDsn: process.env.SENTRY_DSN ?? '',
    eas: {
      projectId: 'abdea07c-f940-4030-b5ed-a3b6e40a51f9',
    },
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
    [
      'expo-build-properties',
      {
        // Allow plain http:// to the LAN/dev backend. Release APKs block
        // cleartext by default (Android 9+); production should use https.
        android: { usesCleartextTraffic: true },
      },
    ],
  ],
});
