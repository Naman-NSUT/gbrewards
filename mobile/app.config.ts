import { ConfigContext, ExpoConfig } from 'expo/config';

// API base URL per environment. Override with API_BASE_URL env at start time, e.g.
//   API_BASE_URL=http://192.168.1.20:8000 npx expo start
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'GB Rewards',
  slug: 'scanrewards',
  scheme: 'scanrewards',
  owner: 'naman04',
  // Stated explicitly rather than inherited from app.json. Google Play removed
  // this app under the Misleading Claims policy for an "app store listing
  // mismatch": the installed icon was still the stock Expo chevron while the
  // listing showed the GoodBed mark. The icon is the thing that got the app
  // pulled, so it is declared where it cannot be lost in a config merge.
  icon: './assets/icon.png',
  android: {
    ...config.android,
    package: 'in.gbrewards.gbrewards',
    adaptiveIcon: {
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
      backgroundColor: '#03132B',
    },
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
    // Hands a downloaded catalogue PDF to whatever PDF viewer the phone has.
    'expo-sharing',
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
