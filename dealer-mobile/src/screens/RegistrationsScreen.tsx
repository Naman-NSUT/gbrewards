import React, { useMemo, useState } from 'react';
import { Pressable, SectionList, StyleSheet, Text, TextInput, View } from 'react-native';

import type { WarrantyOut } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { OfflineBanner } from '../components/OfflineBanner';
import { ScreenBackground } from '../components/ScreenBackground';
import { queueTone, StatusPill, warrantyTone } from '../components/StatusPill';
import { useProducts, useRegistrations } from '../hooks/useDealerData';
import { dismiss, isForeignItem, retry, type QueuedRegistration } from '../offline/queue';
import { useQueue } from '../offline/useQueue';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, radius, spacing } from '../theme';
import { displayStatus, formatDate, formatDateTime, STATUS_LABEL } from '../utils/format';
import { maskPhone } from '../utils/phone';

type Row =
  | { kind: 'queued'; item: QueuedRegistration }
  | { kind: 'warranty'; item: WarrantyOut };

function queueLabel(item: QueuedRegistration): string {
  if (isForeignItem(item)) return 'Other shop';
  if (item.status === 'failed') return 'Not registered';
  if (item.status === 'sending') return 'Sending';
  if (item.status === 'done') {
    return item.resolution === 'registered' ? 'Registered' : 'Already registered';
  }
  return 'Waiting to send';
}

/**
 * The value that identifies one sale on both sides of the wire.
 *
 * This used to be the serial. With nothing scanned, the invoice number is what
 * is left — and it is exactly as good a key, because the server allows one live
 * warranty per (dealer, invoice_ref) and compares it case-insensitively. Matched
 * the same way here so a sale cannot appear twice for want of a capital letter.
 */
function invoiceKey(ref: string | null | undefined): string {
  return (ref ?? '').trim().toLowerCase();
}

function matches(haystack: (string | null | undefined)[], needle: string): boolean {
  if (!needle) return true;
  const query = needle.trim().toLowerCase();
  return haystack.some((value) => (value ?? '').toLowerCase().includes(query));
}

export function RegistrationsScreen({ navigation }: AppTabScreenProps<'Registrations'>) {
  const [query, setQuery] = useState('');
  const registrations = useRegistrations();
  const products = useProducts();
  const { items } = useQueue();

  // The queued body carries a product id, not a name. Naming it costs nothing —
  // the catalogue is already cached for the form — and a row that says only
  // "INV-2043" makes the dealer open it to remember what they sold.
  const productNames = useMemo(() => {
    const byId = new Map<string, string>();
    for (const product of products.data ?? []) byId.set(product.id, product.name);
    return byId;
  }, [products.data]);

  const sections = useMemo(() => {
    // A landed sale stays visible here until the server's own list is carrying
    // it. Otherwise a failed refetch would make a sale the dealer just made
    // vanish from both places — precisely the doubt this screen exists to remove.
    const confirmed = new Set(
      (registrations.data ?? [])
        .map((warranty) => invoiceKey(warranty.invoice_ref))
        .filter(Boolean)
    );
    const unsent = items
      .filter(
        (item) => item.status !== 'done' || !confirmed.has(invoiceKey(item.body.invoice_ref))
      )
      .filter((item) =>
        matches(
          [
            item.body.customer_name,
            item.body.invoice_ref,
            productNames.get(item.body.product_id),
          ],
          query
        )
      )
      .map((item): Row => ({ kind: 'queued', item }));

    const sent = (registrations.data ?? [])
      .filter((warranty) =>
        matches(
          [
            warranty.invoice_ref,
            warranty.model_name,
            warranty.customer?.name,
            warranty.customer?.phone,
          ],
          query
        )
      )
      .map((warranty): Row => ({ kind: 'warranty', item: warranty }));

    return [
      { key: 'unsent', title: 'On this phone', data: unsent },
      { key: 'sent', title: 'Registered', data: sent },
    ].filter((section) => section.data.length > 0);
  }, [items, registrations.data, productNames, query]);

  const nothingAtAll =
    sections.length === 0 && !registrations.isLoading && !registrations.isError;

  return (
    <ScreenBackground>
      <OfflineBanner />
      <View style={styles.searchWrap}>
        <TextInput
          style={styles.search}
          value={query}
          onChangeText={setQuery}
          placeholder="Search invoice, product or customer"
          placeholderTextColor={colors.faint}
          autoCapitalize="none"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />
      </View>

      <SectionList
        sections={sections}
        keyExtractor={(row) => (row.kind === 'queued' ? `q-${row.item.id}` : `w-${row.item.id}`)}
        contentContainerStyle={styles.content}
        stickySectionHeadersEnabled={false}
        refreshing={registrations.isRefetching}
        onRefresh={() => void registrations.refetch()}
        renderSectionHeader={({ section }) => (
          <Text style={styles.sectionTitle}>{section.title}</Text>
        )}
        renderItem={({ item: row }) =>
          row.kind === 'queued' ? (
            <QueuedRow
              item={row.item}
              productName={productNames.get(row.item.body.product_id) ?? null}
              onFix={() =>
                navigation.navigate('Register', {
                  draft: row.item.body,
                  retryOf: row.item.id,
                })
              }
            />
          ) : (
            <WarrantyRow warranty={row.item} />
          )
        }
        ListEmptyComponent={
          nothingAtAll ? (
            <EmptyState
              icon="🛏️"
              title={query ? 'Nothing matches that' : 'No sales registered yet'}
              body={
                query
                  ? 'Try the invoice number, the product, or the customer name.'
                  : 'Register a sale at the counter and it is recorded here.'
              }
              actionLabel={query ? undefined : 'Register a warranty'}
              onAction={query ? undefined : () => navigation.navigate('Register')}
            />
          ) : null
        }
        ListFooterComponent={
          registrations.isError ? (
            <Text style={styles.error}>
              Could not load registrations. Pull down to try again.
            </Text>
          ) : null
        }
      />
    </ScreenBackground>
  );
}

function QueuedRow({
  item,
  productName,
  onFix,
}: {
  item: QueuedRegistration;
  productName: string | null;
  onFix: () => void;
}) {
  const failed = item.status === 'failed';
  return (
    <View style={[styles.card, failed && styles.cardFailed]}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {item.body.customer_name}
        </Text>
        <StatusPill label={queueLabel(item)} tone={queueTone(item)} />
      </View>
      <Text style={styles.cardMeta}>
        {productName ? `${productName} · ` : ''}
        Invoice {item.body.invoice_ref}
      </Text>
      <Text style={styles.cardMeta}>{maskPhone(item.body.customer_phone)}</Text>
      {isForeignItem(item) ? (
        <Text style={styles.cardNote}>
          Made under a different dealership. Sign in with that account to send it.
        </Text>
      ) : item.lastError ? (
        <Text style={[styles.cardNote, failed && styles.cardNoteBad]}>{item.lastError}</Text>
      ) : null}
      {failed ? (
        <View style={styles.actions}>
          <Pressable onPress={onFix} hitSlop={8}>
            <Text style={styles.actionPrimary}>Fix details</Text>
          </Pressable>
          <Pressable onPress={() => retry(item.id)} hitSlop={8}>
            <Text style={styles.actionPrimary}>Try again</Text>
          </Pressable>
          <Pressable onPress={() => dismiss(item.id)} hitSlop={8}>
            <Text style={styles.actionMuted}>Discard</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function WarrantyRow({ warranty }: { warranty: WarrantyOut }) {
  const status = displayStatus(warranty);
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {warranty.customer?.name ?? warranty.model_name ?? 'GoodBed mattress'}
        </Text>
        <StatusPill label={STATUS_LABEL[status]} tone={warrantyTone(status)} />
      </View>
      <Text style={styles.cardMeta}>
        {warranty.model_name ?? 'GoodBed mattress'}
        {warranty.invoice_ref ? ` · Invoice ${warranty.invoice_ref}` : ''}
      </Text>
      <Text style={styles.cardMeta}>
        Covers until {formatDate(warranty.warranty_end_date)}
      </Text>
      <Text style={styles.cardFoot}>Registered {formatDateTime(warranty.registered_at)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  searchWrap: { paddingHorizontal: spacing.md, paddingTop: spacing.md },
  search: {
    height: 46,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    fontSize: 15,
    color: colors.text,
  },
  content: { padding: spacing.md, paddingBottom: spacing.xl * 2 },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  cardFailed: { borderColor: 'rgba(209,77,107,0.45)' },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  cardTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.text },
  cardMeta: { fontSize: 13, color: colors.muted, marginTop: 3 },
  cardFoot: { fontSize: 12, color: colors.faint, marginTop: spacing.sm },
  cardNote: { fontSize: 13, color: colors.muted, marginTop: spacing.sm, lineHeight: 18 },
  cardNoteBad: { color: colors.danger },
  actions: { flexDirection: 'row', gap: spacing.lg, marginTop: spacing.md },
  actionPrimary: { fontSize: 14, fontWeight: '700', color: colors.accent },
  actionMuted: { fontSize: 14, fontWeight: '600', color: colors.muted },
  error: { fontSize: 14, color: colors.danger, textAlign: 'center', marginTop: spacing.lg },
});
