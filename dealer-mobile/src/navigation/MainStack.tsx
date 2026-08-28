import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { ConfirmationScreen } from '../screens/ConfirmationScreen';
import { RegisterScreen } from '../screens/RegisterScreen';
import { colors } from '../theme';
import { AppTabs } from './AppTabs';
import type { MainStackParamList } from './types';

const Stack = createNativeStackNavigator<MainStackParamList>();

export function MainStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        headerTitleAlign: 'center',
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="Tabs" component={AppTabs} options={{ headerShown: false }} />
      <Stack.Screen
        name="Register"
        component={RegisterScreen}
        options={{ title: 'Register a warranty' }}
      />
      {/* No back arrow: the sale is already recorded by the time this shows, and
          walking back into a submitted form invites a second submission. */}
      <Stack.Screen
        name="Confirmation"
        component={ConfirmationScreen}
        options={{ title: 'Sale registered', headerBackVisible: false, gestureEnabled: false }}
      />
    </Stack.Navigator>
  );
}
