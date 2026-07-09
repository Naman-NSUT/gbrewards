import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import type { CompositeScreenProps } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

export type AuthStackParamList = {
  Phone: undefined;
};

export type AuthStackScreenProps<T extends keyof AuthStackParamList> = NativeStackScreenProps<
  AuthStackParamList,
  T
>;

export type AppTabParamList = {
  Home: undefined;
  Redeem: undefined;
  Profile: undefined;
};

export type MainStackParamList = {
  Tabs: undefined;
  Scanner: undefined;
};

export type MainStackScreenProps<T extends keyof MainStackParamList> = NativeStackScreenProps<
  MainStackParamList,
  T
>;

// Tab screens live inside the MainStack, so they can navigate to stack routes
// (e.g. the Scanner modal) via composite navigation.
export type AppTabScreenProps<T extends keyof AppTabParamList> = CompositeScreenProps<
  BottomTabScreenProps<AppTabParamList, T>,
  MainStackScreenProps<keyof MainStackParamList>
>;
