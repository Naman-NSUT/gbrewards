import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button } from '../components/Button';
import { useI18n } from '../i18n/I18nProvider';
import { LANG_LABEL, type Lang } from '../i18n/strings';
import { colors, spacing } from '../theme';

const OPTIONS: { lang: Lang; native: string; sub: string }[] = [
  { lang: 'en', native: 'English', sub: 'Continue in English' },
  { lang: 'hi', native: 'हिंदी', sub: 'हिंदी में जारी रखें' },
];

export function LanguageScreen() {
  const { setLang, t } = useI18n();
  const [selected, setSelected] = useState<Lang>('en');

  return (
    <View style={styles.container}>
      <Text style={styles.brand}>GB Rewards</Text>
      <Text style={styles.title}>{t('lang.title')}</Text>
      <Text style={styles.subtitle}>अपनी भाषा चुनें · Choose your language</Text>

      <View style={{ height: spacing.xl }} />

      {OPTIONS.map((o) => {
        const active = selected === o.lang;
        return (
          <Pressable
            key={o.lang}
            onPress={() => setSelected(o.lang)}
            style={[styles.option, active && styles.optionActive]}
          >
            <View>
              <Text style={styles.optionNative}>{o.native}</Text>
              <Text style={styles.optionSub}>{o.sub}</Text>
            </View>
            <View style={[styles.radio, active && styles.radioActive]}>
              {active && <View style={styles.radioDot} />}
            </View>
          </Pressable>
        );
      })}

      <Button
        title={`${t('lang.continue')} · ${LANG_LABEL[selected]}`}
        onPress={() => setLang(selected)}
        style={{ marginTop: spacing.xl }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: spacing.xl, justifyContent: 'center' },
  brand: { color: colors.primary, fontSize: 15, fontWeight: '700', letterSpacing: 0.5 },
  title: { color: colors.text, fontSize: 28, fontWeight: '800', marginTop: spacing.sm },
  subtitle: { color: colors.muted, fontSize: 14, marginTop: spacing.xs },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: spacing.md,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    marginBottom: spacing.md,
  },
  optionActive: { borderColor: colors.primary, backgroundColor: 'rgba(110,86,207,0.12)' },
  optionNative: { color: colors.text, fontSize: 18, fontWeight: '700' },
  optionSub: { color: colors.muted, fontSize: 13, marginTop: 2 },
  radio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioActive: { borderColor: colors.primary },
  radioDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.primary },
});
