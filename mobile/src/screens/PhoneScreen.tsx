import React, { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { extractApiError } from '../api/client';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { useI18n } from '../i18n/I18nProvider';
import { useRequestOtp } from '../hooks/useLogin';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';
import { formatDobInput, GENDERS, parseDob, PINCODE_RE, type Gender } from '../utils/profile';

const PHONE_RE = /^\+[1-9]\d{7,14}$/;

export function PhoneScreen({ navigation }: AuthStackScreenProps<'Phone'>) {
  const { t } = useI18n();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('+91');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [pincode, setPincode] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState<Gender | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestOtpMutation = useRequestOtp();

  const onSubmit = () => {
    setError(null);

    if (name.trim().length === 0) return setError(t('phone.errName'));
    if (!PHONE_RE.test(phone)) return setError(t('phone.errPhone'));
    if (address.trim().length === 0) return setError(t('phone.errAddress'));
    if (city.trim().length === 0) return setError(t('phone.errCity'));
    if (state.trim().length === 0) return setError(t('phone.errState'));
    if (!PINCODE_RE.test(pincode.trim())) return setError(t('phone.errPincode'));

    // Same rules as the backend (see src/utils/profile.ts) so the user gets a
    // precise message here instead of a generic 422 from the server.
    const isoDob = parseDob(dob);
    if (!isoDob) return setError(t('phone.errDob'));
    if (!gender) return setError(t('phone.errGender'));

    const profile = {
      phone,
      name: name.trim(),
      address: address.trim(),
      city: city.trim(),
      state: state.trim(),
      pincode: pincode.trim(),
      dob: isoDob,
      gender,
    };

    requestOtpMutation.mutate(profile, {
      onSuccess: (res) => navigation.navigate('Otp', { profile, resendIn: res.resend_in }),
      onError: (e) => setError(extractApiError(e)?.message ?? t('phone.errSend')),
    });
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.container}
      >
        <ScrollView contentContainerStyle={styles.inner} keyboardShouldPersistTaps="handled">
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

          <View style={styles.row}>
            <View style={styles.rowItem}>
              <Text style={styles.label}>{t('phone.city')}</Text>
              <TextInput
                style={styles.input}
                placeholder={t('phone.cityPlaceholder')}
                placeholderTextColor={colors.faint}
                value={city}
                onChangeText={setCity}
                autoCapitalize="words"
              />
            </View>
            <View style={styles.rowItem}>
              <Text style={styles.label}>{t('phone.pincode')}</Text>
              <TextInput
                style={styles.input}
                placeholder="411001"
                placeholderTextColor={colors.faint}
                value={pincode}
                onChangeText={(v) => setPincode(v.replace(/\D/g, '').slice(0, 6))}
                keyboardType="number-pad"
                maxLength={6}
              />
            </View>
          </View>

          <Text style={styles.label}>{t('phone.state')}</Text>
          <TextInput
            style={styles.input}
            placeholder={t('phone.statePlaceholder')}
            placeholderTextColor={colors.faint}
            value={state}
            onChangeText={setState}
            autoCapitalize="words"
          />

          <Text style={styles.label}>{t('phone.dob')}</Text>
          <TextInput
            style={styles.input}
            placeholder="DD/MM/YYYY"
            placeholderTextColor={colors.faint}
            value={dob}
            onChangeText={(v) => setDob(formatDobInput(v))}
            keyboardType="number-pad"
            maxLength={10}
          />

          <Text style={styles.label}>{t('phone.gender')}</Text>
          <View style={styles.genderRow}>
            {GENDERS.map((g) => {
              const active = gender === g;
              return (
                <Pressable
                  key={g}
                  onPress={() => setGender(g)}
                  style={[styles.genderBtn, active && styles.genderBtnActive]}
                >
                  <Text style={[styles.genderText, active && styles.genderTextActive]}>
                    {t(`gender.${g}`)}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {error && <Text style={styles.error}>{error}</Text>}

          <Button
            title={t('phone.send')}
            onPress={onSubmit}
            loading={requestOtpMutation.isPending}
            style={{ marginTop: spacing.lg }}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  inner: {
    padding: spacing.xl,
    paddingBottom: spacing.xl * 2,
    flexGrow: 1,
    justifyContent: 'center',
  },
  title: { fontSize: 28, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 16, color: colors.muted, marginTop: spacing.xs, marginBottom: spacing.md },
  label: { fontSize: 13, color: colors.muted, marginTop: spacing.md, marginBottom: spacing.xs },
  input: {
    height: 50,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  addressInput: { height: 80, paddingTop: spacing.sm, textAlignVertical: 'top' },
  row: { flexDirection: 'row', gap: spacing.sm },
  rowItem: { flex: 1 },
  genderRow: { flexDirection: 'row', gap: spacing.sm },
  genderBtn: {
    flex: 1,
    height: 46,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  genderBtnActive: { borderColor: colors.primary, backgroundColor: 'rgba(0,144,216,0.10)' },
  genderText: { color: colors.muted, fontSize: 15, fontWeight: '600' },
  genderTextActive: { color: colors.text },
  error: { color: colors.danger, marginTop: spacing.md },
});
