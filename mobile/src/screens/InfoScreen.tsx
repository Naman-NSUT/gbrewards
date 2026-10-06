import React, { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { CatalogDoc } from '../api/catalogDocs';
import { ScreenBackground } from '../components/ScreenBackground';
import { useCatalogDocs, useOpenCatalogDoc } from '../hooks/useCatalogDocs';
import { useI18n } from '../i18n/I18nProvider';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

/**
 * The Info tab: four catalogue sheets, each rendered by the server from whatever
 * the back office holds at the moment it is tapped.
 *
 * This screen used to draw the four lists itself from the JSON endpoints, which
 * put the formatting of the points table in the app where it could only change
 * with a release. It is now a list of documents; the content is the server's.
 */
function DocRow({
  doc,
  busy,
  error,
  onPress,
}: {
  doc: CatalogDoc;
  busy: boolean;
  error: boolean;
  onPress: () => void;
}) {
  const { t } = useI18n();
  return (
    <Pressable
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel={doc.title}
    >
      <View style={styles.badge}>
        <Text style={styles.badgeText}>PDF</Text>
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle}>{doc.title}</Text>
        <Text style={[styles.rowSubtitle, error && styles.rowSubtitleError]}>
          {error ? t('info.docFailed') : busy ? t('info.docOpening') : doc.subtitle}
        </Text>
      </View>
      {busy ? <ActivityIndicator color={colors.primary} /> : <Text style={styles.chevron}>›</Text>}
    </Pressable>
  );
}

export function InfoScreen(_props: AppTabScreenProps<'Info'>) {
  const { t } = useI18n();
  const docs = useCatalogDocs();
  const open = useOpenCatalogDoc();
  // Which row was tapped, so the spinner and any error land on that row rather
  // than on all four.
  const [active, setActive] = useState<string | null>(null);

  const rows = docs.data ?? [];

  return (
    <ScreenBackground>
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.sectionTitle}>{t('info.documents')}</Text>
        <Text style={styles.lead}>{t('info.documentsLead')}</Text>

        {docs.isLoading ? (
          <ActivityIndicator style={{ marginTop: spacing.lg }} color={colors.primary} />
        ) : docs.isError ? (
          <Text style={styles.empty}>{t('info.docFailed')}</Text>
        ) : rows.length === 0 ? (
          <Text style={styles.empty}>{t('info.empty')}</Text>
        ) : (
          rows.map((doc) => (
            <DocRow
              key={doc.slug}
              doc={doc}
              busy={open.isPending && active === doc.slug}
              error={open.isError && active === doc.slug}
              onPress={() => {
                setActive(doc.slug);
                open.mutate(doc);
              }}
            />
          ))
        )}
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
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
    textTransform: 'uppercase',
  },
  lead: { color: colors.muted, fontSize: 14, marginBottom: spacing.md, lineHeight: 20 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  rowPressed: { backgroundColor: colors.bg },
  badge: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  badgeText: { color: colors.onPrimary, fontSize: 11, fontWeight: '800', letterSpacing: 0.5 },
  rowBody: { flex: 1 },
  rowTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  rowSubtitle: { fontSize: 13, color: colors.muted, marginTop: 2, lineHeight: 18 },
  rowSubtitleError: { color: colors.danger },
  chevron: { fontSize: 26, color: colors.faint, marginLeft: spacing.sm },
  empty: { color: colors.muted, fontSize: 15, marginTop: spacing.md },
});
