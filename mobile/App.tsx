import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as Sentry from '@sentry/react-native';
import Constants from 'expo-constants';
import { StatusBar } from 'expo-status-bar';
import React, { useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from './src/auth/AuthContext';
import { AnimatedSplash } from './src/components/AnimatedSplash';
import { I18nProvider, useI18n } from './src/i18n/I18nProvider';
import { RootNavigator } from './src/navigation/RootNavigator';
import { LanguageScreen } from './src/screens/LanguageScreen';
import { colors } from './src/theme';

const sentryDsn = (Constants.expoConfig?.extra as { sentryDsn?: string } | undefined)?.sentryDsn;
if (sentryDsn) {
  Sentry.init({ dsn: sentryDsn, tracesSampleRate: 0.1 });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 10_000 },
  },
});

function Gate() {
  const { ready, chosen } = useI18n();

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }
  // First launch: ask which language before anything else.
  if (!chosen) return <LanguageScreen />;
  return <RootNavigator />;
}

export default function App() {
  const [splashDone, setSplashDone] = useState(false);

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      {!splashDone ? (
        <AnimatedSplash onDone={() => setSplashDone(true)} />
      ) : (
        <I18nProvider>
          <QueryClientProvider client={queryClient}>
            <AuthProvider>
              <Gate />
            </AuthProvider>
          </QueryClientProvider>
        </I18nProvider>
      )}
    </SafeAreaProvider>
  );
}
