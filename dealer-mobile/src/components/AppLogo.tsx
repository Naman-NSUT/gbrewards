import React from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { colors } from '../theme';

// Wordmark aspect ratio is 720:103 — the same asset the worker app ships.
const ASPECT = 720 / 103;

/**
 * The GoodBed wordmark, with a "Dealer" suffix.
 *
 * The real bitmap rather than type: this header sits at the top of every screen
 * and is the first thing that tells a dealer which product they are in. Hand-set
 * type approximates a logo, it never matches it, and the two apps are meant to
 * read as one family.
 *
 * The suffix stays as text beside it. Both apps are GoodBed, but they are
 * different apps with different accounts, and someone holding both needs to see
 * at a glance which one is open.
 */
export function AppLogo({ height = 22 }: { height?: number }) {
  return (
    <View style={styles.row}>
      <Image
        source={require('../../assets/logo-wordmark.png')}
        resizeMode="contain"
        style={{ height, width: height * ASPECT }}
      />
      <View style={styles.divider} />
      <Text style={[styles.suffix, { fontSize: Math.max(11, height - 8) }]}>Dealer</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center' },
  divider: {
    width: 1,
    height: 14,
    backgroundColor: colors.border,
    marginHorizontal: 8,
  },
  suffix: { color: colors.muted, fontWeight: '600', letterSpacing: 0.6 },
});
