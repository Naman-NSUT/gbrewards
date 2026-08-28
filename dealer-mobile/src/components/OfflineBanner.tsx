import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useIsOnline } from '../offline/net';
import { useQueue } from '../offline/useQueue';
import { colors, spacing } from '../theme';

/**
 * The dealer's answer to "did that sale actually land?".
 *
 * Shown whenever there is anything unresolved, and silent otherwise — a banner
 * that is always on the screen stops being read. Failures outrank queued items:
 * a queued sale needs patience, a failed one needs a person.
 */
export function OfflineBanner({ onPress }: { onPress?: () => void }) {
  const online = useIsOnline();
  const { pendingCount, failedCount, syncing } = useQueue();

  if (failedCount === 0 && pendingCount === 0 && online) return null;

  let tone = styles.info;
  let text: string;
  if (failedCount > 0) {
    tone = styles.danger;
    text = `${failedCount} ${failedCount === 1 ? 'sale needs' : 'sales need'} your attention`;
  } else if (pendingCount > 0) {
    text = online
      ? `Sending ${pendingCount} ${pendingCount === 1 ? 'sale' : 'sales'}…`
      : `${pendingCount} ${pendingCount === 1 ? 'sale' : 'sales'} saved — will send when you're back online`;
    if (!online) tone = styles.warning;
  } else {
    tone = styles.warning;
    text = 'No connection. You can keep registering sales — they are saved on this phone.';
  }

  return (
    <Pressable onPress={onPress} disabled={!onPress}>
      <View style={[styles.bar, tone]}>
        {syncing && online ? (
          <ActivityIndicator size="small" color={colors.primary} style={styles.spinner} />
        ) : null}
        <Text style={styles.text} numberOfLines={2}>
          {text}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  info: { backgroundColor: colors.accentSoft },
  warning: { backgroundColor: 'rgba(192,138,46,0.14)' },
  danger: { backgroundColor: 'rgba(209,77,107,0.12)' },
  spinner: { marginRight: spacing.sm },
  text: { flex: 1, fontSize: 13, fontWeight: '600', color: colors.text },
});
