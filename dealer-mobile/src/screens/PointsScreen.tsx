import React from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';

import type { LedgerEntryOut } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { OfflineBanner } from '../components/OfflineBanner';
import { ScreenBackground } from '../components/ScreenBackground';
import { useLedger, usePointsSummary } from '../hooks/useDealerData';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, radius, spacing } from '../theme';
import { formatDateTime, formatPoints, LEDGER_LABEL } from '../utils/format';

export function PointsScreen({ navigation }: AppTabScreenProps<'Points'>) {
  const summary = usePointsSummary();
  const ledger = useLedger();

  const available = summary.data?.available ?? 0;
  const balance = summary.data?.balance ?? 0;
  const pending = summary.data?.pending ?? 0;
  const earned = summary.data?.total_earned ?? 0;

  return (
    <ScreenBackground>
      <OfflineBanner />
      <FlatList
        data={ledger.data ?? []}
        keyExtractor={(entry) => entry.id}
        contentContainerStyle={styles.content}
        refreshing={summary.isRefetching || ledger.isRefetching}
        onRefresh={() => {
          void summary.refetch();
          void ledger.refetch();
        }}
        ListHeaderComponent={
          <View>
            <View style={styles.hero}>
              <Text style={styles.heroLabel}>Available to spend</Text>
              <Text style={styles.heroValue}>{formatPoints(available)}</Text>
              <Text style={styles.heroMeta}>points</Text>
            </View>

            <View style={styles.stats}>
              <Stat label="Balance" value={balance} />
              <Stat label="On hold" value={pending} hint="Waiting on redemption approval" />
              <Stat label="Earned" value={earned} />
            </View>

            <Text style={styles.sectionTitle}>History</Text>
          </View>
        }
        renderItem={({ item }) => <LedgerRow entry={item} />}
        ListEmptyComponent={
          !ledger.isLoading ? (
            <EmptyState
              icon="🎯"
              title="No points yet"
              body="Every sale you register at the counter earns points for your shop."
              actionLabel="Register a warranty"
              onAction={() => navigation.navigate('Register')}
            />
          ) : null
        }
        ListFooterComponent={
          ledger.isError ? (
            <Text style={styles.error}>Could not load history. Pull down to try again.</Text>
          ) : null
        }
      />
    </ScreenBackground>
  );
}

function Stat({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{formatPoints(value)}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {hint ? <Text style={styles.statHint}>{hint}</Text> : null}
    </View>
  );
}

function LedgerRow({ entry }: { entry: LedgerEntryOut }) {
  const credit = entry.amount > 0;
  return (
    <View style={styles.row}>
      <View style={styles.rowMain}>
        <Text style={styles.rowTitle}>{LEDGER_LABEL[entry.type] ?? 'Points adjustment'}</Text>
        {/* The serial this row came from is no longer shown: sales registered
            since the dropdown replaced the scanner do not have one, and on the
            ones that do it is a code the dealer can no longer look up anywhere
            in this app. The label and date are what identify the entry now. */}
        {entry.reason ? <Text style={styles.rowMeta}>{entry.reason}</Text> : null}
        <Text style={styles.rowDate}>{formatDateTime(entry.created_at)}</Text>
      </View>
      <Text style={[styles.amount, credit ? styles.credit : styles.debit]}>
        {credit ? '+' : '−'}
        {formatPoints(Math.abs(entry.amount))}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl * 2 },
  hero: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    alignItems: 'flex-start',
  },
  heroLabel: { color: 'rgba(255,255,255,0.75)', fontSize: 13, fontWeight: '600' },
  heroValue: {
    color: '#fff',
    fontSize: 44,
    fontWeight: '800',
    letterSpacing: -1,
    marginTop: spacing.xs,
  },
  heroMeta: { color: 'rgba(255,255,255,0.75)', fontSize: 13 },
  stats: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  stat: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  statValue: { fontSize: 20, fontWeight: '800', color: colors.text },
  statLabel: { fontSize: 12, color: colors.muted, marginTop: 2, fontWeight: '600' },
  statHint: { fontSize: 11, color: colors.faint, marginTop: 2, lineHeight: 15 },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.md,
  },
  rowMain: { flex: 1 },
  rowTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  rowMeta: { fontSize: 13, color: colors.muted, marginTop: 2 },
  rowDate: { fontSize: 12, color: colors.faint, marginTop: 4 },
  amount: { fontSize: 17, fontWeight: '800' },
  credit: { color: colors.success },
  debit: { color: colors.danger },
  error: { fontSize: 14, color: colors.danger, textAlign: 'center', marginTop: spacing.lg },
});
