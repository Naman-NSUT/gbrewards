import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { AppLogo } from '../components/AppLogo';
import { OtpScreen } from '../screens/OtpScreen';
import { PhoneScreen } from '../screens/PhoneScreen';
import { colors } from '../theme';
import type { AuthStackParamList } from './types';

const Stack = createNativeStackNavigator<AuthStackParamList>();

export function AuthStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        headerTitleAlign: 'center',
        headerTitle: () => <AppLogo />,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="Phone" component={PhoneScreen} options={{ headerShown: false }} />
      <Stack.Screen
        name="Otp"
        component={OtpScreen}
        options={{ headerShown: true, headerBackTitle: '' }}
      />
    </Stack.Navigator>
  );
}
