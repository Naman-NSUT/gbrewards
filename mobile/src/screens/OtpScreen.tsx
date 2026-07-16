import React, { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { extractApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { useI18n } from '../i18n/I18nProvider';
import { useRequestOtp, useVerifyOtp } from '../hooks/useLogin';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

const CODE_RE = /^\d{4,8}$/;

export function OtpScreen({ route }: AuthStackScreenProps<'Otp'>) {
  const { phone, name, address, resendIn } = route.params;
  const { t } = useI18n();
  const { signIn } = useAuth();
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(resendIn);
  const verifyMutation = useVerifyOtp();
  const resendMutation = useRequestOtp();

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  const onVerify = () => {
    setError(null);
    if (!CODE_RE.test(code.trim())) {
      setError(t('otp.errCode'));
      return;
    }
    verifyMutation.mutate(
      { phone, code: code.trim() },
      {
        onSuccess: (tokens) =>
          signIn({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token }),
        onError: (e) => setError(extractApiError(e)?.message ?? t('otp.errVerify')),
      }
    );
  };

  const onResend = () => {
    if (cooldown > 0) return;
    setError(null);
    resendMutation.mutate(
      { phone, name, address },
      {
        onSuccess: (res) => setCooldown(res.resend_in),
        onError: (e) => setError(extractApiError(e)?.message ?? t('otp.errVerify')),
      }
    );
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.container}
      >
        <View style={styles.inner}>
        <Text style={styles.title}>{t('otp.title')}</Text>
        <Text style={styles.subtitle}>{t('otp.subtitle', { phone })}</Text>

        <Text style={styles.label}>{t('otp.code')}</Text>
        <TextInput
          style={styles.input}
          placeholder="••••••"
          placeholderTextColor={colors.faint}
          value={code}
          onChangeText={setCode}
          keyboardType="number-pad"
          maxLength={8}
          autoFocus
          textContentType="oneTimeCode"
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <Button
          title={t('otp.verify')}
          onPress={onVerify}
          loading={verifyMutation.isPending}
          style={{ marginTop: spacing.lg }}
        />

        <Pressable onPress={onResend} disabled={cooldown > 0} style={styles.resend}>
          <Text style={[styles.resendText, cooldown > 0 && styles.resendDisabled]}>
            {cooldown > 0 ? t('otp.resendIn', { s: String(cooldown) }) : t('otp.resend')}
          </Text>
        </Pressable>
        </View>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  inner: { flex: 1, padding: spacing.xl, justifyContent: 'center' },
  title: { fontSize: 28, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 16, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.xl },
  label: { fontSize: 13, color: colors.muted, marginTop: spacing.md, marginBottom: spacing.xs },
  input: {
    height: 50,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    fontSize: 22,
    letterSpacing: 8,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  error: { color: colors.danger, marginTop: spacing.md },
  resend: { marginTop: spacing.lg, alignItems: 'center' },
  resendText: { color: colors.primary, fontSize: 15, fontWeight: '600' },
  resendDisabled: { color: colors.muted },
});
