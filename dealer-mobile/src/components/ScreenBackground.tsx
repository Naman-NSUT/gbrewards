import { LinearGradient } from 'expo-linear-gradient';
import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { colors } from '../theme';

interface Props {
  children?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

// The same aurora wash the GB Rewards app uses: a soft top-to-bottom base plus
// large, very-low-opacity navy/cyan glows bleeding off the corners. Shared
// deliberately — a dealer who has seen the worker app should recognise this one.
export function ScreenBackground({ children, style }: Props) {
  return (
    <View style={[styles.root, style]}>
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        <LinearGradient
          colors={[colors.surface, colors.bg]}
          start={{ x: 0.5, y: 0 }}
          end={{ x: 0.5, y: 1 }}
          style={StyleSheet.absoluteFill}
        />
        <View style={[styles.blob, styles.blobCyanTop]} />
        <View style={[styles.blob, styles.blobNavyBottom]} />
        <View style={[styles.blob, styles.blobCyanMid]} />
      </View>
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  content: { flex: 1 },
  blob: {
    position: 'absolute',
    width: 360,
    height: 360,
    borderRadius: 360,
  },
  blobCyanTop: { top: -140, right: -120, backgroundColor: 'rgba(0,144,216,0.10)' },
  blobNavyBottom: { bottom: -160, left: -130, backgroundColor: 'rgba(24,72,96,0.08)' },
  blobCyanMid: {
    top: '40%',
    left: -170,
    width: 300,
    height: 300,
    borderRadius: 300,
    backgroundColor: 'rgba(0,144,216,0.05)',
  },
});
