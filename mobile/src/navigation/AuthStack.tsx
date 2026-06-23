import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { useI18n } from '../i18n/I18nProvider';
import { OtpScreen } from '../screens/OtpScreen';
import { PhoneScreen } from '../screens/PhoneScreen';
import { colors } from '../theme';
import type { AuthStackParamList } from './types';

const Stack = createNativeStackNavigator<AuthStackParamList>();

export function AuthStack() {
  const { t } = useI18n();
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="Phone" component={PhoneScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Otp" component={OtpScreen} options={{ title: t('otp.verify') }} />
    </Stack.Navigator>
  );
}
