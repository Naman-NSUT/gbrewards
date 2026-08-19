import { ConfigContext, ExpoConfig } from 'expo/config';

// API base URL per environment. Override with API_BASE_URL at start time, e.g.
//   API_BASE_URL=http://192.168.1.20:8000 npx expo start
// 10.0.2.2 is the host loopback as seen from the Android emulator.
export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'GoodBed Dealer',
  slug: 'dealerrewards',
  scheme: 'dealerrewards',
  orientation: 'portrait',
  userInterfaceStyle: 'light',
  android: {
    ...config.android,
    package: 'in.goodbed.dealerrewards',
  },
  ios: {
    ...config.ios,
    bundleIdentifier: 'in.goodbed.dealerrewards',
    supportsTablet: false,
  },
  extra: {
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://10.0.2.2:8000',
    // EAS project on the GoodBed Expo account. Required for cloud builds; the
    // config is dynamic (TS), so eas init cannot write this itself.
    eas: {
      projectId: 'cf907108-984d-46e4-b3f9-29640b477a88',
    },
  },
  plugins: [
    [
      'expo-camera',
      {
        cameraPermission:
          'GoodBed Dealer uses the camera to scan the QR code on a mattress label.',
        // This app only ever reads a QR code. Asking a shopkeeper for microphone
        // access to register a mattress is the kind of thing that gets an app
        // uninstalled, so the default RECORD_AUDIO permission is dropped.
        recordAudioAndroid: false,
        microphonePermission: false,
      },
    ],
    'expo-secure-store',
    [
      'expo-build-properties',
      {
        // Allow plain http:// to a LAN/dev backend. Release builds block
        // cleartext by default (Android 9+); production must use https.
        android: { usesCleartextTraffic: true },
      },
    ],
  ],
});
