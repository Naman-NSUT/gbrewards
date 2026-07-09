import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { extractApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { useI18n } from '../i18n/I18nProvider';
import { useLogin } from '../hooks/useLogin';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

const PHONE_RE = /^\+[1-9]\d{7,14}$/;

export function PhoneScreen(_props: AuthStackScreenProps<'Phone'>) {
  const { t } = useI18n();
  const { signIn } = useAuth();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('+91');
  const [address, setAddress] = useState('');
  const [error, setError] = useState<string | null>(null);
  const loginMutation = useLogin();

  const onSubmit = () => {
    setError(null);
    if (!PHONE_RE.test(phone)) {
      setError(t('phone.errPhone'));
      return;
    }
    if (name.trim().length === 0) {
      setError(t('phone.errName'));
      return;
    }
    if (address.trim().length === 0) {
      setError(t('phone.errAddress'));
      return;
    }

    loginMutation.mutate(
      { phone, name: name.trim(), address: address.trim() },
      {
        onSuccess: (tokens) =>
          signIn({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token }),
        onError: (e) => {
          setError(extractApiError(e)?.message ?? t('phone.errSend'));
        },
      }
    );
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.container}
    >
      <View style={styles.inner}>
        <Text style={styles.title}>{t('phone.title')}</Text>
        <Text style={styles.subtitle}>{t('phone.subtitle')}</Text>

        <Text style={styles.label}>{t('phone.name')}</Text>
        <TextInput
          style={styles.input}
          placeholder={t('phone.namePlaceholder')}
          placeholderTextColor={colors.faint}
          value={name}
          onChangeText={setName}
          autoCapitalize="words"
        />

        <Text style={styles.label}>{t('phone.phone')}</Text>
        <TextInput
          style={styles.input}
          placeholder="+9199…"
          placeholderTextColor={colors.faint}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          autoCapitalize="none"
        />

        <Text style={styles.label}>{t('phone.address')}</Text>
        <TextInput
          style={[styles.input, styles.addressInput]}
          placeholder={t('phone.addressPlaceholder')}
          placeholderTextColor={colors.faint}
          value={address}
          onChangeText={setAddress}
          multiline
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <Button
          title={t('phone.continue')}
          onPress={onSubmit}
          loading={loginMutation.isPending}
          style={{ marginTop: spacing.lg }}
        />
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
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
    fontSize: 16,
    color: colors.text,
  },
  addressInput: { height: 80, paddingTop: spacing.sm, textAlignVertical: 'top' },
  error: { color: colors.danger, marginTop: spacing.md },
});
