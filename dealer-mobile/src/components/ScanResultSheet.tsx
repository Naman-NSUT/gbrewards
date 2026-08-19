import React from 'react';
import { ActivityIndicator, Modal, StyleSheet, Text, View } from 'react-native';

import type { UnitPreviewOut } from '../api/types';
import { colors, radius, spacing } from '../theme';
import { shortSerial } from '../utils/serial';
import { Button } from './Button';
import { StatusPill } from './StatusPill';

export type ScanOutcome =
  | { kind: 'checking'; serial: string }
  | { kind: 'preview'; serial: string; preview: UnitPreviewOut }
  // The preview could not be reached. NOT a dead end: the allocation check the
  // preview would have run also runs server-side at registration, so the dealer
  // records the sale now and the answer arrives when the queue drains.
  | { kind: 'unchecked'; serial: string; message: string }
  | { kind: 'error'; serial: string; title: string; message: string }
  | null;

interface Props {
  outcome: ScanOutcome;
  onDismiss: () => void;
  onContinue: (serial: string, preview: UnitPreviewOut | null) => void;
}

export function ScanResultSheet({ outcome, onDismiss, onContinue }: Props) {
  return (
    <Modal
      visible={outcome !== null}
      transparent
      animationType="slide"
      onRequestClose={onDismiss}
      statusBarTranslucent
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.grabber} />

          {outcome?.kind === 'checking' ? (
            <View style={styles.centered}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.checking}>Checking this unit…</Text>
              <Text style={styles.serial}>{shortSerial(outcome.serial)}</Text>
            </View>
          ) : null}

          {outcome?.kind === 'preview' ? (
            <>
              <View style={styles.headerRow}>
                <Text style={styles.model} numberOfLines={2}>
                  {outcome.preview.model_name ?? 'GoodBed mattress'}
                </Text>
                <StatusPill
                  label={outcome.preview.registerable ? 'Ready to register' : 'Cannot register'}
                  tone={outcome.preview.registerable ? 'success' : 'danger'}
                />
              </View>
              <Text style={styles.serial}>{shortSerial(outcome.preview.serial)}</Text>
              <Text style={styles.meta}>
                {outcome.preview.warranty_months} month warranty
              </Text>
              {outcome.preview.reason ? (
                <Text
                  style={[
                    styles.reason,
                    outcome.preview.registerable ? styles.reasonNeutral : styles.reasonBad,
                  ]}
                >
                  {outcome.preview.reason}
                </Text>
              ) : null}
              {outcome.preview.registerable ? (
                <Button
                  title="Add customer details"
                  size="lg"
                  onPress={() => onContinue(outcome.preview.serial, outcome.preview)}
                  style={styles.primaryAction}
                />
              ) : null}
              <Button
                title={outcome.preview.registerable ? 'Cancel' : 'Scan another unit'}
                variant="secondary"
                onPress={onDismiss}
                style={styles.secondaryAction}
              />
            </>
          ) : null}

          {outcome?.kind === 'unchecked' ? (
            <>
              <View style={styles.headerRow}>
                <Text style={styles.model}>Offline</Text>
                <StatusPill label="Not checked" tone="warning" />
              </View>
              <Text style={styles.serial}>{shortSerial(outcome.serial)}</Text>
              <Text style={styles.reason}>{outcome.message}</Text>
              <Button
                title="Record the sale anyway"
                size="lg"
                onPress={() => onContinue(outcome.serial, null)}
                style={styles.primaryAction}
              />
              <Button
                title="Cancel"
                variant="secondary"
                onPress={onDismiss}
                style={styles.secondaryAction}
              />
            </>
          ) : null}

          {outcome?.kind === 'error' ? (
            <>
              <View style={styles.headerRow}>
                <Text style={styles.model}>{outcome.title}</Text>
                <StatusPill label="Error" tone="danger" />
              </View>
              <Text style={styles.serial}>{shortSerial(outcome.serial)}</Text>
              <Text style={[styles.reason, styles.reasonBad]}>{outcome.message}</Text>
              <Button
                title="Scan another unit"
                variant="secondary"
                onPress={onDismiss}
                style={styles.primaryAction}
              />
            </>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(14,51,70,0.45)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl + spacing.md,
  },
  grabber: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: spacing.lg,
  },
  centered: { alignItems: 'center', paddingVertical: spacing.lg },
  checking: { marginTop: spacing.md, fontSize: 16, fontWeight: '600', color: colors.text },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  model: { flex: 1, fontSize: 20, fontWeight: '800', color: colors.text },
  serial: {
    fontSize: 13,
    color: colors.muted,
    marginTop: spacing.xs,
    letterSpacing: 0.6,
  },
  meta: { fontSize: 14, color: colors.text, marginTop: spacing.sm },
  reason: { fontSize: 14, color: colors.muted, marginTop: spacing.sm, lineHeight: 20 },
  reasonNeutral: { color: colors.muted },
  reasonBad: { color: colors.danger },
  primaryAction: { marginTop: spacing.lg },
  secondaryAction: { marginTop: spacing.sm },
});
