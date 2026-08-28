import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { errorMessage } from '../api/client';
import { AppLogo } from '../components/AppLogo';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { TextField } from '../components/TextField';
import { useRequestOtp } from '../hooks/useLogin';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';
import { digitsOf, normalisePhone } from '../utils/phone';

export function PhoneScreen({ navigation }: AuthStackScreenProps<'Phone'>) {
  const insets = useSafeAreaInsets();
  const [phone, setPhone] = useState('');
  const [error, setError] = useState<string | null>(null);
  const requestOtpMutation = useRequestOtp();

  const onSubmit = () => {
    setError(null);
    const normalised = normalisePhone(phone);
    if (!normalised) {
      setError('Enter the 10-digit mobile number GoodBed registered for you.');
      return;
    }
    requestOtpMutation.mutate(normalised, {
      onSuccess: (res) =>
        {
          // No account for this number: sending them to the OTP screen would be
          // a dead end, because no code was generated. Take them where they can
          // actually get in, with the number they already typed.
          if (res.account_exists === false) {
            navigation.navigate('Signup', { phone: normalised });
            return;
          }
          navigation.navigate('Otp', { phone: normalised, resendIn: res.resend_in });
        },
      onError: (e) => setError(errorMessage(e, 'Could not send the code. Try again.')),
    });
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={[styles.inner, { paddingTop: insets.top + spacing.xl }]}
          keyboardShouldPersistTaps="handled"
        >
          <AppLogo height={30} />
          <Text style={styles.title}>Register a sale in seconds</Text>
          <Text style={styles.subtitle}>
            Scan the mattress QR at the counter, add the customer, and the warranty starts on
            the right day — and you earn points for it.
          </Text>

          <TextField
            label="Mobile number"
            value={phone}
            onChangeText={(value) => setPhone(digitsOf(value).slice(0, 12))}
            placeholder="98765 43210"
            keyboardType="number-pad"
            autoCapitalize="none"
            maxLength={12}
            autoFocus
            returnKeyType="go"
            onSubmitEditing={onSubmit}
            error={error}
            hint="We'll text you a 6-digit code."
          />

          <Button
            title="Send code"
            size="lg"
            onPress={onSubmit}
            loading={requestOtpMutation.isPending}
            style={styles.action}
          />

          <View style={styles.note}>
            <Text style={styles.noteText}>New to GoodBed Dealer?</Text>
            <Text
              style={styles.link}
              onPress={() => navigation.navigate('Signup')}
              accessibilityRole="button"
            >
              Create your shop account
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  inner: {
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xl * 2,
    flexGrow: 1,
    justifyContent: 'center',
  },
  title: {
    fontSize: 30,
    fontWeight: '800',
    color: colors.text,
    marginTop: spacing.xl,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 16,
    color: colors.muted,
    marginTop: spacing.sm,
    lineHeight: 23,
  },
  action: { marginTop: spacing.lg },
  note: {
    marginTop: spacing.xl,
    padding: spacing.md,
    backgroundColor: colors.accentSoft,
    borderRadius: 12,
  },
  link: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.accent,
    marginTop: 6,
    paddingVertical: 6,
  },
  noteText: { fontSize: 13, color: colors.text, lineHeight: 19 },
});
