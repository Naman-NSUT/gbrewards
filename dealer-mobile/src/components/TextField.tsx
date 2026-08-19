import React from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  View,
  type KeyboardTypeOptions,
  type ReturnKeyTypeOptions,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { colors, radius, spacing } from '../theme';

interface Props {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  placeholder?: string;
  /** Shown inline under the field. Validation belongs next to what it judges. */
  error?: string | null;
  hint?: string;
  optional?: boolean;
  keyboardType?: KeyboardTypeOptions;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  autoFocus?: boolean;
  maxLength?: number;
  multiline?: boolean;
  returnKeyType?: ReturnKeyTypeOptions;
  onSubmitEditing?: () => void;
  inputRef?: React.RefObject<TextInput | null>;
  style?: StyleProp<ViewStyle>;
}

export function TextField({
  label,
  value,
  onChangeText,
  placeholder,
  error,
  hint,
  optional = false,
  keyboardType,
  autoCapitalize = 'sentences',
  autoFocus = false,
  maxLength,
  multiline = false,
  returnKeyType,
  onSubmitEditing,
  inputRef,
  style,
}: Props) {
  return (
    <View style={[styles.wrap, style]}>
      <View style={styles.labelRow}>
        <Text style={styles.label}>{label}</Text>
        {optional ? <Text style={styles.optional}>optional</Text> : null}
      </View>
      <TextInput
        ref={inputRef}
        style={[
          styles.input,
          multiline && styles.multiline,
          error ? styles.inputError : null,
        ]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.faint}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
        autoFocus={autoFocus}
        maxLength={maxLength}
        multiline={multiline}
        returnKeyType={returnKeyType}
        onSubmitEditing={onSubmitEditing}
        blurOnSubmit={!multiline}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {!error && hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing.md },
  labelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { fontSize: 13, fontWeight: '600', color: colors.muted, marginBottom: spacing.xs },
  optional: { fontSize: 12, color: colors.faint, marginBottom: spacing.xs },
  input: {
    height: 52,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    fontSize: 17,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  multiline: { height: 84, paddingTop: spacing.sm, textAlignVertical: 'top' },
  inputError: { borderColor: colors.danger },
  error: { fontSize: 13, color: colors.danger, marginTop: spacing.xs },
  hint: { fontSize: 12, color: colors.faint, marginTop: spacing.xs },
});
