import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { Text } from 'react-native';

import { AppLogo } from '../components/AppLogo';
import { useQueue } from '../offline/useQueue';
import { HomeScreen } from '../screens/HomeScreen';
import { PointsScreen } from '../screens/PointsScreen';
import { ProfileScreen } from '../screens/ProfileScreen';
import { RegistrationsScreen } from '../screens/RegistrationsScreen';
import { RewardsScreen } from '../screens/RewardsScreen';
import { ScanScreen } from '../screens/ScanScreen';
import { colors } from '../theme';
import type { AppTabParamList } from './types';

const Tab = createBottomTabNavigator<AppTabParamList>();

const ICONS: Record<keyof AppTabParamList, string> = {
  Home: '🏠',
  Scan: '📷',
  Registrations: '🧾',
  Points: '⭐',
  Rewards: '🎁',
  Profile: '👤',
};

const TITLES: Record<keyof AppTabParamList, string> = {
  Home: 'Home',
  Scan: 'Scan',
  Registrations: 'Sales',
  Points: 'Points',
  Rewards: 'Rewards',
  Profile: 'Profile',
};

export function AppTabs() {
  const { pendingCount, failedCount } = useQueue();
  // One number, on the tab that can act on it. A dealer must never have to guess
  // whether a sale actually landed.
  const unsent = pendingCount + failedCount;

  return (
    <Tab.Navigator
      initialRouteName="Home"
      screenOptions={({ route }) => ({
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        headerStyle: { backgroundColor: colors.surface },
        headerShadowVisible: false,
        headerTintColor: colors.text,
        headerTitleAlign: 'center',
        headerTitle: () => <AppLogo />,
        title: TITLES[route.name],
        tabBarIcon: ({ focused }) => (
          <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.55 }}>{ICONS[route.name]}</Text>
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} />
      {/* The scanner owns the whole viewport: a header above a camera would push
          the frame under the dealer's thumb. It is one tap from Home, and Home
          leads with a scan button, so the counter flow is still two taps. */}
      <Tab.Screen name="Scan" component={ScanScreen} options={{ headerShown: false }} />
      <Tab.Screen
        name="Registrations"
        component={RegistrationsScreen}
        options={{
          tabBarBadge: unsent > 0 ? unsent : undefined,
          tabBarBadgeStyle: {
            backgroundColor: failedCount > 0 ? colors.danger : colors.accent,
            color: '#fff',
            fontSize: 11,
          },
        }}
      />
      <Tab.Screen name="Points" component={PointsScreen} />
      <Tab.Screen name="Rewards" component={RewardsScreen} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}
