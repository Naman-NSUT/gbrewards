import type { NativeStackScreenProps } from '@react-navigation/native-stack';

export type AuthStackParamList = {
  Phone: undefined;
  Otp: { phone: string; name: string };
};

export type AuthStackScreenProps<T extends keyof AuthStackParamList> = NativeStackScreenProps<
  AuthStackParamList,
  T
>;

export type AppTabParamList = {
  Scan: undefined;
  History: undefined;
  Redeem: undefined;
  Profile: undefined;
};
