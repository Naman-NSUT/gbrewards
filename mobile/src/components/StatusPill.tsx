import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { RedemptionStatus } from '../api/types';
import { colors, spacing } from '../theme';

const STATUS_COLOR: Record<RedemptionStatus, string> = {
  pending: colors.warning,
  approved: colors.primary,
  fulfilled: colors.success,
  rejected: colors.danger,
  cancelled: colors.muted,
};

export function StatusPill({ status, label }: { status: RedemptionStatus; label: string }) {
  return (
    <View style={[styles.pill, { backgroundColor: STATUS_COLOR[status] }]}>
      <Text style={styles.pillText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    borderRadius: 12,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginLeft: spacing.sm,
  },
  pillText: { color: '#fff', fontSize: 12, fontWeight: '600' },
});
