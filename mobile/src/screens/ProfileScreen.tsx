import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { useMe, useUpdateProfile } from '../hooks/useMe';
import { useI18n } from '../i18n/I18nProvider';
import { LANG_LABEL, type Lang } from '../i18n/strings';
import { colors, spacing } from '../theme';

const LANGS: Lang[] = ['en', 'hi'];

export function ProfileScreen() {
  const { t, lang, setLang } = useI18n();
  const me = useMe();
  const updateProfile = useUpdateProfile();
  const { signOut } = useAuth();
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const [addressDraft, setAddressDraft] = useState<string | null>(null);

  const serverName = me.data?.name ?? '';
  const serverAddress = me.data?.address ?? '';
  const name = nameDraft ?? serverName;
  const address = addressDraft ?? serverAddress;

  const nameValid = name.trim().length > 0;
  const dirty =
    (nameDraft !== null && name.trim() !== serverName) ||
    (addressDraft !== null && address.trim() !== serverAddress);

  const onSave = () => {
    if (!nameValid) return;
    updateProfile.mutate(
      { name: name.trim(), address: address.trim() },
      {
        onSuccess: () => {
          setNameDraft(null);
          setAddressDraft(null);
        },
      }
    );
  };

  return (
    <View style={styles.container}>
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

      <Button
        title={t('profile.save')}
        onPress={onSave}
        loading={updateProfile.isPending}
        disabled={!dirty || !nameValid}
        style={{ marginTop: spacing.md }}
      />

      <Text style={styles.label}>{t('lang.label')}</Text>
      <View style={styles.langRow}>
        {LANGS.map((l) => {
          const active = lang === l;
          return (
            <Pressable
              key={l}
              onPress={() => setLang(l)}
              style={[styles.langBtn, active && styles.langBtnActive]}
            >
              <Text style={[styles.langText, active && styles.langTextActive]}>{LANG_LABEL[l]}</Text>
            </Pressable>
          );
        })}
      </View>

      <View style={{ flex: 1 }} />

      <Button title={t('profile.logout')} variant="secondary" onPress={() => void signOut()} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: spacing.xl },
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
  },
  addressInput: { height: 80, paddingTop: spacing.sm, textAlignVertical: 'top' },
  langRow: { flexDirection: 'row', gap: spacing.sm },
  langBtn: {
    flex: 1,
    height: 46,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  langBtnActive: { borderColor: colors.primary, backgroundColor: 'rgba(110,86,207,0.12)' },
  langText: { color: colors.muted, fontSize: 15, fontWeight: '600' },
  langTextActive: { color: colors.text },
});
