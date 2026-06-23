import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { extractApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { useI18n } from '../i18n/I18nProvider';
import { useRequestOtp, useVerifyOtp } from '../hooks/useOtp';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

const RESEND_SECONDS = 30;

export function OtpScreen({ route }: AuthStackScreenProps<'Otp'>) {
  const { phone, name } = route.params;
  const { t } = useI18n();
  const { signIn } = useAuth();
  const verifyOtp = useVerifyOtp();
  const requestOtp = useRequestOtp();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(RESEND_SECONDS);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const onVerify = () => {
    setError(null);
    verifyOtp.mutate(
      { phone, code },
      {
        onSuccess: (tokens) => {
          void signIn({
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
          });
        },
        onError: (e) => {
          const api = extractApiError(e);
          setError(api?.message ?? t('otp.errInvalid'));
        },
      }
    );
  };

  const onResend = () => {
    setError(null);
    requestOtp.mutate(
      { phone, name },
      {
        onSuccess: () => setCooldown(RESEND_SECONDS),
        onError: (e) => {
          const api = extractApiError(e);
          setError(api?.message ?? t('otp.errResend'));
        },
      }
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t('otp.title')}</Text>
      <Text style={styles.subtitle}>{t('otp.subtitle', { phone })}</Text>

      <TextInput
        style={styles.input}
        placeholder="••••••"
        placeholderTextColor={colors.faint}
        value={code}
        onChangeText={setCode}
        keyboardType="number-pad"
        maxLength={6}
        textAlign="center"
      />

      {error && <Text style={styles.error}>{error}</Text>}

      <Button
        title={t('otp.verify')}
        onPress={onVerify}
        loading={verifyOtp.isPending}
        disabled={code.length < 4}
        style={{ marginTop: spacing.lg }}
      />
      <Button
        title={cooldown > 0 ? t('otp.resendIn', { s: cooldown }) : t('otp.resend')}
        onPress={onResend}
        variant="secondary"
        disabled={cooldown > 0 || requestOtp.isPending}
        style={{ marginTop: spacing.md }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: spacing.xl, justifyContent: 'center' },
  title: { fontSize: 28, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 16, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl },
  input: {
    height: 64,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    fontSize: 28,
    letterSpacing: 8,
    color: colors.text,
  },
  error: { color: colors.danger, marginTop: spacing.md },
});
