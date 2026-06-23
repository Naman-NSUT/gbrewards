import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { Text } from 'react-native';

import { useI18n } from '../i18n/I18nProvider';
import { HistoryScreen } from '../screens/HistoryScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { RedeemScreen } from '../screens/RedeemScreen';
import { ScanScreen } from '../screens/ScanScreen';
import { colors } from '../theme';
import type { AppTabParamList } from './types';

const Tab = createBottomTabNavigator<AppTabParamList>();

const ICONS: Record<keyof AppTabParamList, string> = {
  Scan: '📷',
  History: '📊',
  Redeem: '🎁',
  Profile: '👤',
};

const LABEL_KEY: Record<keyof AppTabParamList, string> = {
  Scan: 'tab.scan',
  History: 'tab.history',
  Redeem: 'tab.redeem',
  Profile: 'tab.profile',
};

export function AppTabs() {
  const { t } = useI18n();
  return (
    <Tab.Navigator
      initialRouteName="Scan"
      screenOptions={({ route }) => ({
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        title: t(LABEL_KEY[route.name]),
        tabBarIcon: ({ focused }) => (
          <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.5 }}>{ICONS[route.name]}</Text>
        ),
      })}
    >
      <Tab.Screen name="Scan" component={ScanScreen} />
      <Tab.Screen name="History" component={HistoryScreen} />
      <Tab.Screen name="Redeem" component={RedeemScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}
