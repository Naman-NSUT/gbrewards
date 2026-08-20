import React, { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { errorCode, errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { TextField } from '../components/TextField';
import { useRequestOtp, useVerifyOtp } from '../hooks/useLogin';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';
import { digitsOf, formatPhone } from '../utils/phone';

/**
 * The backend answers `/auth/otp/request` identically for a known and an unknown
 * number — it must not become a way to discover which numbers are dealers. So
 * "we don't know you" can only surface here, and it has to be a friendly,
 * actionable sentence rather than a 403.
 */
function messageFor(error: unknown): string {
  switch (errorCode(error)) {
    case 'account_not_found':
      return 'This number is not set up as a GoodBed dealer yet. Ask your GoodBed representative to add it, then try again.';
    case 'dealer_inactive':
      return 'Your dealership is not active right now. Please contact GoodBed.';
    case 'otp_invalid':
      return 'That code is not right. Check the SMS and try again.';
    case 'otp_expired':
      return 'That code has expired. Tap Resend to get a new one.';
    case 'otp_attempts_exceeded':
      return 'Too many wrong attempts. Request a new code.';
    default:
      return errorMessage(error, 'Could not verify the code. Try again.');
  }
}

export function OtpScreen({ route, navigation }: AuthStackScreenProps<'Otp'>) {
  const { phone, resendIn, isNewAccount } = route.params;
  const { signIn } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  // A signup arrives without a cooldown; fall back to the server default so
  // the resend timer still behaves.
  const [cooldown, setCooldown] = useState(resendIn ?? 30);
  const verifyMutation = useVerifyOtp();
  const resendMutation = useRequestOtp();

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  const onVerify = (value: string) => {
    setError(null);
    if (value.length !== 6) {
      setError('Enter the 6-digit code.');
      return;
    }
    verifyMutation.mutate(
      { phone, code: value },
      {
        onSuccess: (tokens) => void signIn(tokens),
        onError: (e) => setError(messageFor(e)),
      }
    );
  };

  const onResend = () => {
    if (cooldown > 0) return;
    setError(null);
    resendMutation.mutate(phone, {
      onSuccess: (res) => setCooldown(res.resend_in),
      onError: (e) => setError(errorMessage(e, 'Could not resend the code.')),
    });
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
      >
        <View style={styles.inner}>
          <Text style={styles.title}>Enter the code</Text>
          <Text style={styles.subtitle}>Sent to {formatPhone(phone)}</Text>

          <TextField
            label="6-digit code"
            value={code}
            onChangeText={(value) => {
              const next = digitsOf(value).slice(0, 6);
              setCode(next);
              // Submit the moment it is complete: one less tap at a counter.
              if (next.length === 6) onVerify(next);
            }}
            placeholder="••••••"
            keyboardType="number-pad"
            autoCapitalize="none"
            maxLength={6}
            autoFocus
            error={error}
          />

          <Button
            title="Verify and sign in"
            size="lg"
            onPress={() => onVerify(code)}
            loading={verifyMutation.isPending}
            style={styles.action}
          />

          <View style={styles.footer}>
            <Pressable onPress={onResend} disabled={cooldown > 0 || resendMutation.isPending}>
              <Text style={[styles.link, cooldown > 0 && styles.linkDisabled]}>
                {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}
              </Text>
            </Pressable>
            <Pressable onPress={() => navigation.goBack()}>
              <Text style={styles.link}>Change number</Text>
            </Pressable>
          </View>
        </View>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  inner: { flex: 1, paddingHorizontal: spacing.xl, justifyContent: 'center' },
  title: { fontSize: 28, fontWeight: '800', color: colors.text, letterSpacing: -0.4 },
  subtitle: { fontSize: 16, color: colors.muted, marginTop: spacing.xs },
  action: { marginTop: spacing.lg },
  footer: {
    marginTop: spacing.lg,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  link: { color: colors.accent, fontSize: 15, fontWeight: '600' },
  linkDisabled: { color: colors.faint },
});
