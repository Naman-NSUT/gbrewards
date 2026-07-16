import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ScreenBackground } from '../components/ScreenBackground';
import { useFaqs, useProductPoints, useTerms } from '../hooks/useContent';
import { useRewards } from '../hooks/useRewards';
import { useI18n } from '../i18n/I18nProvider';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

export function InfoScreen(_props: AppTabScreenProps<'Info'>) {
  const { t } = useI18n();
  const products = useProductPoints();
  const rewards = useRewards();
  const faqs = useFaqs();
  const terms = useTerms();
  const [open, setOpen] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const productRows = products.data ?? [];
  const rewardRows = rewards.data ?? [];
  const faqRows = faqs.data ?? [];

  return (
    <ScreenBackground>
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>{t('info.products')}</Text>
      {productRows.length === 0 && !products.isLoading ? (
        <Text style={styles.empty}>{t('info.empty')}</Text>
      ) : (
        productRows.map((p) => (
          <View key={p.id} style={styles.row}>
            <Text style={styles.rowLabel}>{p.name}</Text>
            <Text style={styles.rowValue}>
              {p.points_value} {t('info.pointsSuffix')}
            </Text>
          </View>
        ))
      )}

      <Text style={styles.sectionTitle}>{t('info.rewards')}</Text>
      {rewardRows.length === 0 && !rewards.isLoading ? (
        <Text style={styles.empty}>{t('info.empty')}</Text>
      ) : (
        rewardRows.map((r) => (
          <View key={r.id} style={styles.row}>
            <View style={styles.rewardInfo}>
              <Text style={styles.rowLabel}>{r.title}</Text>
              {r.description ? <Text style={styles.rewardDesc}>{r.description}</Text> : null}
            </View>
            <Text style={styles.rowValue}>
              {r.points_cost} {t('info.pointsSuffix')}
            </Text>
          </View>
        ))
      )}

      <Text style={styles.sectionTitle}>{t('info.faqs')}</Text>
      {faqRows.length === 0 && !faqs.isLoading ? (
        <Text style={styles.empty}>{t('info.empty')}</Text>
      ) : (
        faqRows.map((f) => {
          const expanded = open.has(f.id);
          return (
            <View key={f.id} style={styles.faqItem}>
              <Pressable style={styles.faqHeader} onPress={() => toggle(f.id)}>
                <Text style={styles.faqQuestion}>{f.question}</Text>
                <Text style={styles.faqChevron}>{expanded ? '−' : '+'}</Text>
              </Pressable>
              {expanded ? <Text style={styles.faqAnswer}>{f.answer}</Text> : null}
            </View>
          );
        })
      )}

      <Text style={styles.sectionTitle}>{t('info.terms')}</Text>
      {terms.data ? (
        <View style={styles.termsBlock}>
          <Text style={styles.termsTitle}>{terms.data.title}</Text>
          <Text style={styles.termsBody}>{terms.data.body}</Text>
        </View>
      ) : !terms.isLoading ? (
        <Text style={styles.empty}>{t('info.empty')}</Text>
      ) : null}
      </ScrollView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.md },
  sectionTitle: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowLabel: { fontSize: 15, fontWeight: '600', color: colors.text, flex: 1 },
  rowValue: { fontSize: 15, fontWeight: '700', color: colors.primary, marginLeft: spacing.md },
  rewardInfo: { flex: 1 },
  rewardDesc: { fontSize: 13, color: colors.muted, marginTop: 2 },
  faqItem: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  faqHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
  },
  faqQuestion: { fontSize: 15, fontWeight: '600', color: colors.text, flex: 1 },
  faqChevron: { fontSize: 20, color: colors.muted, marginLeft: spacing.md },
  faqAnswer: { fontSize: 14, color: colors.muted, paddingBottom: spacing.md, lineHeight: 20 },
  termsBlock: { paddingVertical: spacing.sm },
  termsTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: spacing.sm },
  termsBody: { fontSize: 14, color: colors.muted, lineHeight: 20 },
  empty: { color: colors.muted, fontSize: 15, marginTop: spacing.sm },
});
