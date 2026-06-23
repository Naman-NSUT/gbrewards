import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { useMe, useUpdateName } from '../hooks/useMe';
import { useI18n } from '../i18n/I18nProvider';
import { LANG_LABEL, type Lang } from '../i18n/strings';
import { colors, spacing } from '../theme';

const LANGS: Lang[] = ['en', 'hi'];

export function ProfileScreen() {
  const { t, lang, setLang } = useI18n();
  const me = useMe();
  const updateName = useUpdateName();
  const { signOut } = useAuth();
  const [draft, setDraft] = useState<string | null>(null);

  const serverName = me.data?.name ?? '';
  const name = draft ?? serverName;
  const dirty = draft !== null && name.trim() !== serverName && name.trim().length > 0;

  const onSave = () => {
    updateName.mutate(name.trim(), { onSuccess: () => setDraft(null) });
  };

  return (
    <View style={styles.container}>
      <Text style={styles.label}>{t('profile.phone')}</Text>
      <Text style={styles.value}>{me.data?.phone ?? '—'}</Text>

      <Text style={styles.label}>{t('profile.name')}</Text>
      <TextInput style={styles.input} value={name} onChangeText={setDraft} autoCapitalize="words" />

      <Button
        title={t('profile.save')}
        onPress={onSave}
        loading={updateName.isPending}
        disabled={!dirty}
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
