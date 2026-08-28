import React from 'react';
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import type { RedemptionStatus } from '../api/types';
import type { QueuedRegistration } from '../offline/queue';
import { colors, spacing } from '../theme';
import type { DisplayStatus } from '../utils/format';

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

// Soft tint + coloured text rather than the solid pills used on the worker app's
// single-status screens: these lists show a dozen rows at once, and a dozen solid
// blocks of colour turn a scannable list into a fruit salad.
const TONE: Record<Tone, { bg: string; fg: string }> = {
  success: { bg: 'rgba(30,158,106,0.12)', fg: '#14724C' },
  warning: { bg: 'rgba(192,138,46,0.14)', fg: '#8A6117' },
  danger: { bg: 'rgba(209,77,107,0.12)', fg: '#A83552' },
  info: { bg: colors.accentSoft, fg: '#0A5E8C' },
  neutral: { bg: 'rgba(24,72,96,0.08)', fg: colors.muted },
};

export function warrantyTone(status: DisplayStatus): Tone {
  switch (status) {
    case 'active':
      return 'success';
    case 'claimed':
      return 'info';
    case 'voided':
      return 'danger';
    case 'expired':
      return 'neutral';
    default:
      return 'warning'; // Everything pending is waiting on a human somewhere.
  }
}

export function redemptionTone(status: RedemptionStatus): Tone {
  switch (status) {
    case 'fulfilled':
      return 'success';
    case 'approved':
      return 'info';
    case 'rejected':
      return 'danger';
    case 'cancelled':
      return 'neutral';
    default:
      return 'warning';
  }
}

export function queueTone(item: QueuedRegistration): Tone {
  if (item.status === 'failed') return 'danger';
  if (item.status === 'done') return item.resolution === 'registered' ? 'success' : 'warning';
  return 'info';
}

export function StatusPill({
  label,
  tone = 'neutral',
  style,
}: {
  label: string;
  tone?: Tone;
  style?: StyleProp<ViewStyle>;
}) {
  const palette = TONE[tone];
  return (
    <View style={[styles.pill, { backgroundColor: palette.bg }, style]}>
      <Text style={[styles.text, { color: palette.fg }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    // Matched to the worker app's pill so a status reads identically in both:
    // same corner, same padding, same weight.
    borderRadius: 12,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    alignSelf: 'flex-start',
  },
  text: { fontSize: 12, fontWeight: '600', letterSpacing: 0.2 },
});
