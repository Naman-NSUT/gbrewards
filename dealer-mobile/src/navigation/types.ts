import type { BottomTabScreenProps } from '@react-navigation/bottom-tabs';
import type { CompositeScreenProps, NavigatorScreenParams } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { RegisterBody } from '../api/types';

export type AuthStackParamList = {
  Phone: undefined;
  Signup: { phone?: string } | undefined;
  Otp: { phone: string; resendIn?: number; isNewAccount?: boolean };
};

export type AuthStackScreenProps<T extends keyof AuthStackParamList> = NativeStackScreenProps<
  AuthStackParamList,
  T
>;

export type AppTabParamList = {
  Home: undefined;
  Registrations: undefined;
  Points: undefined;
  Rewards: undefined;
  Profile: undefined;
};

export type MainStackParamList = {
  Tabs: NavigatorScreenParams<AppTabParamList> | undefined;
  /**
   * The registration form. Takes no parameters for a new sale — there is no
   * scanned unit to hand it any more, the dealer picks the product on the form.
   */
  Register:
    | {
        /** Prefill when correcting a submission the server rejected. */
        draft?: RegisterBody;
        /** Queue id being corrected — replaced (new key) on submit, never reused. */
        retryOf?: string;
      }
    | undefined;
  Confirmation: { queueId: string };
};

export type MainStackScreenProps<T extends keyof MainStackParamList> = NativeStackScreenProps<
  MainStackParamList,
  T
>;

// Tab screens live inside MainStack, so they can push stack routes.
export type AppTabScreenProps<T extends keyof AppTabParamList> = CompositeScreenProps<
  BottomTabScreenProps<AppTabParamList, T>,
  MainStackScreenProps<keyof MainStackParamList>
>;
