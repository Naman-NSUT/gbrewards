import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors, radius } from '../theme';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface Props {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: Variant;
  /** Counter-height target for the one action the dealer must hit first time. */
  size?: 'md' | 'lg';
  style?: StyleProp<ViewStyle>;
}

export function Button({
  title,
  onPress,
  loading = false,
  disabled = false,
  variant = 'primary',
  size = 'md',
  style,
}: Props) {
  const isDisabled = disabled || loading;
  const spinnerColor = variant === 'primary' || variant === 'danger' ? '#fff' : colors.primary;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        size === 'lg' && styles.large,
        VARIANT_STYLE[variant],
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={spinnerColor} />
      ) : (
        <Text style={[styles.text, TEXT_STYLE[variant], size === 'lg' && styles.textLarge]}>
          {title}
        </Text>
      )}
    </Pressable>
  );
}

const VARIANT_STYLE: Record<Variant, ViewStyle> = {
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  ghost: { backgroundColor: 'transparent' },
  danger: { backgroundColor: colors.danger },
};

const TEXT_STYLE = StyleSheet.create({
  primary: { color: colors.onPrimary },
  secondary: { color: colors.primary },
  ghost: { color: colors.primary },
  danger: { color: colors.onPrimary },
});

const styles = StyleSheet.create({
  base: {
    height: 50,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  large: { height: 58, borderRadius: radius.lg },
  pressed: { opacity: 0.85 },
  disabled: { opacity: 0.45 },
  text: { fontSize: 16, fontWeight: '600' },
  textLarge: { fontSize: 18, fontWeight: '700' },
});
