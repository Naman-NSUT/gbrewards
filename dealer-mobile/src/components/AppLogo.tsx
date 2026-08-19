import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors } from '../theme';

/**
 * Wordmark set in type rather than shipped as a bitmap: the header is the only
 * place it appears, and a text mark stays sharp on every density without adding
 * an asset that has to be kept in sync with the brand's own logo files.
 */
export function AppLogo({ size = 18 }: { size?: number }) {
  return (
    <View style={styles.row}>
      <Text style={[styles.good, { fontSize: size }]}>Good</Text>
      <Text style={[styles.bed, { fontSize: size }]}>Bed</Text>
      <View style={styles.divider} />
      <Text style={[styles.suffix, { fontSize: size - 4 }]}>Dealer</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  good: { color: colors.primary, fontWeight: '800', letterSpacing: -0.3 },
  bed: { color: colors.accent, fontWeight: '800', letterSpacing: -0.3 },
  divider: {
    width: 1,
    height: 14,
    backgroundColor: colors.border,
    marginHorizontal: 8,
  },
  suffix: { color: colors.muted, fontWeight: '600', letterSpacing: 0.6 },
});
