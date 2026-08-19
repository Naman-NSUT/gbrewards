import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider } from './src/auth/AuthContext';
import { useQueueQuerySync } from './src/hooks/useDealerData';
import { useQueueRuntime } from './src/offline/useQueue';
import { RootNavigator } from './src/navigation/RootNavigator';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // One retry, then show what we have. A dealer on a bad connection needs
      // the screen to settle, not to spin — the queue is what guarantees the
      // write; reads can simply be stale.
      retry: 1,
      staleTime: 15_000,
      refetchOnWindowFocus: true,
    },
  },
});

function Shell() {
  useQueueRuntime();
  useQueueQuerySync();
  return <RootNavigator />;
}

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <Shell />
        </AuthProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
