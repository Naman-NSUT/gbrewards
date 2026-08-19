import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';
import { Button } from './Button';

interface Props {
  icon?: string;
  title: string;
  body?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon = '📋', title, body, actionLabel, onAction }: Props) {
  return (
    <View style={styles.root}>
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.title}>{title}</Text>
      {body ? <Text style={styles.body}>{body}</Text> : null}
      {actionLabel && onAction ? (
        <Button
          title={actionLabel}
          variant="secondary"
          onPress={onAction}
          style={styles.action}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { alignItems: 'center', paddingVertical: spacing.xl, paddingHorizontal: spacing.lg },
  icon: { fontSize: 40, marginBottom: spacing.sm },
  title: { fontSize: 17, fontWeight: '700', color: colors.text, textAlign: 'center' },
  body: {
    fontSize: 14,
    color: colors.muted,
    textAlign: 'center',
    marginTop: spacing.xs,
    lineHeight: 20,
  },
  action: { marginTop: spacing.lg, minWidth: 200 },
});
