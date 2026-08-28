import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import type { DealerProduct } from '../api/types';
import { colors, radius, spacing } from '../theme';
import { Button } from './Button';

interface Props {
  products: DealerProduct[];
  /** The chosen product id, or null before the dealer has picked. */
  value: string | null;
  onChange: (productId: string) => void;
  loading?: boolean;
  /** Set when the catalogue could not be loaded AND nothing was cached. */
  loadError?: string | null;
  onRetry?: () => void;
  error?: string | null;
}

/** Above this, a shop is scrolling rather than reading, so give them a filter. */
const SEARCH_THRESHOLD = 8;

function subtitle(product: DealerProduct): string {
  const parts = [product.model_code, `${product.warranty_months} month warranty`];
  return parts.filter(Boolean).join(' · ');
}

/**
 * The field that replaced the scanner.
 *
 * A full-screen list rather than a wheel or an inline dropdown: this is the one
 * choice on the form that cannot be corrected later without voiding a warranty,
 * and it is made across a counter with a customer waiting. Each row therefore
 * carries the model code printed on the box and the cover length, which is how a
 * shop assistant tells a 36-month model from a 60-month one of the same name.
 */
export function ProductPicker({
  products,
  value,
  onChange,
  loading = false,
  loadError = null,
  onRetry,
  error = null,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const selected = products.find((product) => product.id === value) ?? null;

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return products;
    return products.filter(
      (product) =>
        product.name.toLowerCase().includes(needle) ||
        (product.model_code ?? '').toLowerCase().includes(needle)
    );
  }, [products, query]);

  const close = () => {
    setOpen(false);
    setQuery('');
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>Product</Text>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel={selected ? `Product: ${selected.name}` : 'Choose the product sold'}
        accessibilityState={{ expanded: open, disabled: loading }}
        onPress={() => setOpen(true)}
        disabled={loading}
        style={[styles.field, error ? styles.fieldError : null]}
      >
        <View style={styles.fieldText}>
          {loading ? (
            <Text style={styles.placeholder}>Loading products…</Text>
          ) : selected ? (
            <>
              <Text style={styles.value} numberOfLines={1}>
                {selected.name}
              </Text>
              <Text style={styles.valueMeta} numberOfLines={1}>
                {subtitle(selected)}
              </Text>
            </>
          ) : (
            <Text style={styles.placeholder}>Choose what you sold</Text>
          )}
        </View>
        {loading ? (
          <ActivityIndicator size="small" color={colors.muted} />
        ) : (
          <Text style={styles.chevron}>▾</Text>
        )}
      </Pressable>

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {!error && loadError ? <Text style={styles.error}>{loadError}</Text> : null}
      {loadError && onRetry ? (
        <Pressable onPress={onRetry} hitSlop={8}>
          <Text style={styles.retry}>Try loading the products again</Text>
        </Pressable>
      ) : null}

      <Modal visible={open} animationType="slide" onRequestClose={close} transparent>
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <View style={styles.grabber} />
            <Text style={styles.sheetTitle}>What did you sell?</Text>

            {products.length > SEARCH_THRESHOLD ? (
              <TextInput
                style={styles.search}
                value={query}
                onChangeText={setQuery}
                placeholder="Search by name or model code"
                placeholderTextColor={colors.faint}
                autoCapitalize="none"
                autoCorrect={false}
                clearButtonMode="while-editing"
              />
            ) : null}

            <FlatList
              data={visible}
              keyExtractor={(product) => product.id}
              keyboardShouldPersistTaps="handled"
              style={styles.list}
              renderItem={({ item }) => {
                const isSelected = item.id === value;
                return (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityState={{ selected: isSelected }}
                    onPress={() => {
                      onChange(item.id);
                      close();
                    }}
                    style={[styles.option, isSelected && styles.optionSelected]}
                  >
                    <View style={styles.optionText}>
                      <Text style={styles.optionName} numberOfLines={2}>
                        {item.name}
                      </Text>
                      <Text style={styles.optionMeta} numberOfLines={1}>
                        {subtitle(item)}
                      </Text>
                    </View>
                    {isSelected ? <Text style={styles.tick}>✓</Text> : null}
                  </Pressable>
                );
              }}
              ListEmptyComponent={
                <Text style={styles.empty}>
                  {query
                    ? 'No product matches that.'
                    : 'No products available. Ask GoodBed to add your range.'}
                </Text>
              }
            />

            <Button title="Cancel" variant="ghost" onPress={close} style={styles.cancel} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing.md },
  label: { fontSize: 13, fontWeight: '600', color: colors.muted, marginBottom: spacing.xs },
  field: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
  },
  fieldError: { borderColor: colors.danger },
  fieldText: { flex: 1 },
  value: { fontSize: 17, color: colors.text, fontWeight: '600' },
  valueMeta: { fontSize: 12, color: colors.muted, marginTop: 2 },
  placeholder: { fontSize: 17, color: colors.faint },
  chevron: { fontSize: 16, color: colors.muted },
  error: { fontSize: 13, color: colors.danger, marginTop: spacing.xs },
  retry: { fontSize: 13, fontWeight: '700', color: colors.accent, marginTop: spacing.xs },
  backdrop: { flex: 1, backgroundColor: 'rgba(14,51,70,0.45)', justifyContent: 'flex-end' },
  sheet: {
    maxHeight: '85%',
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
  },
  grabber: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    marginBottom: spacing.md,
  },
  sheetTitle: { fontSize: 20, fontWeight: '800', color: colors.text },
  search: {
    height: 46,
    marginTop: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    fontSize: 15,
    color: colors.text,
  },
  list: { marginTop: spacing.sm },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    // Counter-height rows: a mis-tap here registers the wrong mattress.
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  optionSelected: { backgroundColor: colors.accentSoft },
  optionText: { flex: 1 },
  optionName: { fontSize: 16, fontWeight: '600', color: colors.text },
  optionMeta: { fontSize: 13, color: colors.muted, marginTop: 2 },
  tick: { fontSize: 18, fontWeight: '800', color: colors.accent },
  empty: {
    fontSize: 14,
    color: colors.muted,
    textAlign: 'center',
    paddingVertical: spacing.xl,
    lineHeight: 20,
  },
  cancel: { marginTop: spacing.sm },
});
