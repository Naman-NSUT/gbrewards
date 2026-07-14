import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { Text } from 'react-native';

import { useI18n } from '../i18n/I18nProvider';
import { HomeScreen } from '../screens/HomeScreen';
import { InfoScreen } from '../screens/InfoScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { RewardsScreen } from '../screens/RewardsScreen';
import { colors } from '../theme';
import type { AppTabParamList } from './types';

const Tab = createBottomTabNavigator<AppTabParamList>();

const ICONS: Record<keyof AppTabParamList, string> = {
  Home: '🏠',
  Rewards: '🎁',
  Info: 'ℹ️',
  Profile: '👤',
};

const LABEL_KEY: Record<keyof AppTabParamList, string> = {
  Home: 'tab.home',
  Rewards: 'tab.rewards',
  Info: 'tab.info',
  Profile: 'tab.profile',
};

export function AppTabs() {
  const { t } = useI18n();
  return (
    <Tab.Navigator
      initialRouteName="Home"
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
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="Rewards" component={RewardsScreen} />
      <Tab.Screen name="Info" component={InfoScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}
