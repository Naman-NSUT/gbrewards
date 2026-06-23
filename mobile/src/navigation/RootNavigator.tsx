import { NavigationContainer } from '@react-navigation/native';
import React from 'react';
import { ActivityIndicator, View } from 'react-native';

import { useAuth } from '../auth/AuthContext';
import { colors } from '../theme';
import { AppTabs } from './AppTabs';
import { AuthStack } from './AuthStack';

export function RootNavigator() {
  const { isReady, isAuthenticated } = useAuth();

  if (!isReady) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      {isAuthenticated ? <AppTabs /> : <AuthStack />}
    </NavigationContainer>
  );
}
