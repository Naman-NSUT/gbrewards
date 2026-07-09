import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { useI18n } from '../i18n/I18nProvider';
import { ScanScreen } from '../screens/ScanScreen';
import { colors } from '../theme';
import { AppTabs } from './AppTabs';
import type { MainStackParamList } from './types';

const Stack = createNativeStackNavigator<MainStackParamList>();

export function MainStack() {
  const { t } = useI18n();
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="Tabs" component={AppTabs} options={{ headerShown: false }} />
      <Stack.Screen
        name="Scanner"
        component={ScanScreen}
        options={{ title: t('tab.scan'), presentation: 'fullScreenModal' }}
      />
    </Stack.Navigator>
  );
}
