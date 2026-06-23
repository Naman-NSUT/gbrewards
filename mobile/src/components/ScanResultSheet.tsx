import React from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';

import type { ScanClaimResult } from '../api/types';
import { useI18n } from '../i18n/I18nProvider';
import { colors, spacing } from '../theme';
import { Button } from './Button';

export type ScanOutcome =
  | { kind: 'success'; result: ScanClaimResult }
  | { kind: 'duplicate'; claimedAt: string | null }
  | { kind: 'error'; title: string; message: string }
  | null;

function formatDate(iso: string | null): string {
  if (!iso) return 'earlier';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function ScanResultSheet({
  outcome,
  onDismiss,
}: {
  outcome: ScanOutcome;
  onDismiss: () => void;
}) {
  const { t } = useI18n();
  const visible = outcome !== null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          {outcome?.kind === 'success' && (
            <>
              <Text style={[styles.emoji]}>✅</Text>
              <Text style={styles.title}>
                {outcome.result.idempotent ? t('result.alreadyYours') : t('result.earned')}
              </Text>
              <Text style={styles.product}>{outcome.result.product.name}</Text>
              <Text style={[styles.big, { color: colors.success }]}>
                +{outcome.result.points_awarded} pts
              </Text>
              <Text style={styles.muted}>
                {t('result.newBalance', { n: outcome.result.balance })}
              </Text>
            </>
          )}

          {outcome?.kind === 'duplicate' && (
            <>
              <Text style={styles.emoji}>⚠️</Text>
              <Text style={styles.title}>{t('result.duplicateTitle')}</Text>
              <Text style={styles.muted}>
                {t('result.duplicateBody', { date: formatDate(outcome.claimedAt) })}
              </Text>
            </>
          )}

          {outcome?.kind === 'error' && (
            <>
              <Text style={styles.emoji}>❌</Text>
              <Text style={styles.title}>{outcome.title}</Text>
              <Text style={styles.muted}>{outcome.message}</Text>
            </>
          )}

          <Button title={t('result.scanAnother')} onPress={onDismiss} style={{ marginTop: spacing.lg }} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: spacing.xl,
    alignItems: 'center',
  },
  emoji: { fontSize: 48, marginBottom: spacing.sm },
  title: { fontSize: 22, fontWeight: '700', color: colors.text, marginBottom: spacing.xs },
  product: { fontSize: 16, color: colors.text, marginBottom: spacing.sm },
  big: { fontSize: 36, fontWeight: '800', marginVertical: spacing.sm },
  muted: { fontSize: 14, color: colors.muted, textAlign: 'center' },
});
