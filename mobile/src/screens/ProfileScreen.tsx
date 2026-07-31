import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { useMe, useUpdateProfile } from '../hooks/useMe';
import { useI18n } from '../i18n/I18nProvider';
import { LANG_LABEL, type Lang } from '../i18n/strings';
import { colors, spacing } from '../theme';
import {
  formatDobFromApi,
  formatDobInput,
  GENDERS,
  parseDob,
  PINCODE_RE,
  type Gender,
} from '../utils/profile';

const LANGS: Lang[] = ['en', 'hi'];

export function ProfileScreen() {
  const { t, lang, setLang } = useI18n();
  const me = useMe();
  const updateProfile = useUpdateProfile();
  const { signOut } = useAuth();

  // Each field is null until edited, then the draft wins over the server value.
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [addressDraft, setAddressDraft] = useState<string | null>(null);
  const [cityDraft, setCityDraft] = useState<string | null>(null);
  const [stateDraft, setStateDraft] = useState<string | null>(null);
  const [pincodeDraft, setPincodeDraft] = useState<string | null>(null);
  const [dobDraft, setDobDraft] = useState<string | null>(null);
  const [genderDraft, setGenderDraft] = useState<Gender | null>(null);
  const [error, setError] = useState<string | null>(null);

  const serverName = me.data?.name ?? '';
  const serverAddress = me.data?.address ?? '';
  const serverCity = me.data?.city ?? '';
  const serverState = me.data?.state ?? '';
  const serverPincode = me.data?.pincode ?? '';
  const serverDob = formatDobFromApi(me.data?.dob);
  const serverGender = me.data?.gender ?? null;

  const name = nameDraft ?? serverName;
  const address = addressDraft ?? serverAddress;
  const city = cityDraft ?? serverCity;
  const state = stateDraft ?? serverState;
  const pincode = pincodeDraft ?? serverPincode;
  const dob = dobDraft ?? serverDob;
  const gender = genderDraft ?? serverGender;

  const dirty =
    (nameDraft !== null && name.trim() !== serverName) ||
    (addressDraft !== null && address.trim() !== serverAddress) ||
    (cityDraft !== null && city.trim() !== serverCity) ||
    (stateDraft !== null && state.trim() !== serverState) ||
    (pincodeDraft !== null && pincode.trim() !== serverPincode) ||
    (dobDraft !== null && dob.trim() !== serverDob) ||
    (genderDraft !== null && genderDraft !== serverGender);

  const clearDrafts = () => {
    setNameDraft(null);
    setAddressDraft(null);
    setCityDraft(null);
    setStateDraft(null);
    setPincodeDraft(null);
    setDobDraft(null);
    setGenderDraft(null);
  };

  const onSave = () => {
    setError(null);
    if (name.trim().length === 0) return setError(t('phone.errName'));
    if (pincode.trim().length > 0 && !PINCODE_RE.test(pincode.trim())) {
      return setError(t('phone.errPincode'));
    }

    // Only send a DOB when one is present and valid; empty means "leave as is".
    let isoDob: string | undefined;
    if (dob.trim().length > 0) {
      const parsed = parseDob(dob);
      if (!parsed) return setError(t('phone.errDob'));
      isoDob = parsed;
    }

    updateProfile.mutate(
      {
        name: name.trim(),
        address: address.trim(),
        city: city.trim(),
        state: state.trim(),
        pincode: pincode.trim(),
        dob: isoDob,
        gender: gender ?? undefined,
      },
      { onSuccess: clearDrafts, onError: () => setError(t('profile.errSave')) }
    );
  };

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>{t('profile.phone')}</Text>
        <Text style={styles.value}>{me.data?.phone ?? '—'}</Text>

        <Text style={styles.label}>{t('profile.name')}</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setNameDraft}
          autoCapitalize="words"
        />

        <Text style={styles.label}>{t('profile.address')}</Text>
        <TextInput
          style={[styles.input, styles.addressInput]}
          value={address}
          onChangeText={setAddressDraft}
          placeholder={t('phone.addressPlaceholder')}
          placeholderTextColor={colors.faint}
          multiline
        />

        <View style={styles.row}>
          <View style={styles.rowItem}>
            <Text style={styles.label}>{t('phone.city')}</Text>
            <TextInput
              style={styles.input}
              value={city}
              onChangeText={setCityDraft}
              placeholder={t('phone.cityPlaceholder')}
              placeholderTextColor={colors.faint}
              autoCapitalize="words"
            />
          </View>
          <View style={styles.rowItem}>
            <Text style={styles.label}>{t('phone.pincode')}</Text>
            <TextInput
              style={styles.input}
              value={pincode}
              onChangeText={(v) => setPincodeDraft(v.replace(/\D/g, '').slice(0, 6))}
              placeholder="411001"
              placeholderTextColor={colors.faint}
              keyboardType="number-pad"
              maxLength={6}
            />
          </View>
        </View>

        <Text style={styles.label}>{t('phone.state')}</Text>
        <TextInput
          style={styles.input}
          value={state}
          onChangeText={setStateDraft}
          placeholder={t('phone.statePlaceholder')}
          placeholderTextColor={colors.faint}
          autoCapitalize="words"
        />

        <Text style={styles.label}>{t('phone.dob')}</Text>
        <TextInput
          style={styles.input}
          value={dob}
          onChangeText={(v) => setDobDraft(formatDobInput(v))}
          placeholder="DD/MM/YYYY"
          placeholderTextColor={colors.faint}
          keyboardType="number-pad"
          maxLength={10}
        />

        <Text style={styles.label}>{t('phone.gender')}</Text>
        <View style={styles.pickRow}>
          {GENDERS.map((g) => {
            const active = gender === g;
            return (
              <Pressable
                key={g}
                onPress={() => setGenderDraft(g)}
                style={[styles.pickBtn, active && styles.pickBtnActive]}
              >
                <Text style={[styles.pickText, active && styles.pickTextActive]}>
                  {t(`gender.${g}`)}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {error && <Text style={styles.error}>{error}</Text>}

        <Button
          title={t('profile.save')}
          onPress={onSave}
          loading={updateProfile.isPending}
          disabled={!dirty || name.trim().length === 0}
          style={{ marginTop: spacing.md }}
        />

        <Text style={styles.label}>{t('lang.label')}</Text>
        <View style={styles.pickRow}>
          {LANGS.map((l) => {
            const active = lang === l;
            return (
              <Pressable
                key={l}
                onPress={() => setLang(l)}
                style={[styles.pickBtn, active && styles.pickBtnActive]}
              >
                <Text style={[styles.pickText, active && styles.pickTextActive]}>
                  {LANG_LABEL[l]}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Button
          title={t('profile.logout')}
          variant="secondary"
          onPress={() => void signOut()}
          style={{ marginTop: spacing.xl }}
        />
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: 'transparent',
    padding: spacing.xl,
    paddingBottom: spacing.xl * 2,
  },
  label: { fontSize: 13, color: colors.muted, marginTop: spacing.md, marginBottom: spacing.xs },
  value: { fontSize: 17, color: colors.text },
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
  pickRow: { flexDirection: 'row', gap: spacing.sm },
  pickBtn: {
    flex: 1,
    height: 46,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pickBtnActive: { borderColor: colors.primary, backgroundColor: 'rgba(0,144,216,0.10)' },
  pickText: { color: colors.muted, fontSize: 15, fontWeight: '600' },
  pickTextActive: { color: colors.text },
  error: { color: colors.danger, marginTop: spacing.md },
});
