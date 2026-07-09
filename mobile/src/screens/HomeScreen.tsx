import React from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import type { LedgerEntry } from '../api/types';
import { Button } from '../components/Button';
import { useLedger } from '../hooks/useLedger';
import { useMe } from '../hooks/useMe';
import { useI18n } from '../i18n/I18nProvider';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

function LedgerRow({ entry }: { entry: LedgerEntry }) {
  const { t } = useI18n();
  const positive = entry.amount >= 0;
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{t(`ledger.${entry.type}`)}</Text>
        <Text style={styles.rowDate}>{new Date(entry.created_at).toLocaleString()}</Text>
      </View>
      <Text style={[styles.amount, { color: positive ? colors.success : colors.danger }]}>
        {positive ? '+' : ''}
        {entry.amount}
      </Text>
    </View>
  );
}

export function HomeScreen({ navigation }: AppTabScreenProps<'Home'>) {
  const { t } = useI18n();
  const me = useMe();
  const ledger = useLedger();

  const entries = ledger.data?.pages.flatMap((p) => p.items) ?? [];

  const header = (
    <View>
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>{t('history.balance')}</Text>
        <Text style={styles.balanceValue}>{me.data?.balance ?? '—'} pts</Text>
        {me.data && me.data.available !== me.data.balance && (
          <Text style={styles.available}>{t('history.available', { n: me.data.available })}</Text>
        )}
      </View>

      <Button
        title={t('home.scan')}
        onPress={() => navigation.navigate('Scanner')}
        style={styles.scanButton}
      />

      <Text style={styles.sectionTitle}>{t('home.history')}</Text>
    </View>
  );

  return (
    <FlatList
      style={styles.container}
      data={entries}
      keyExtractor={(e) => e.id}
      renderItem={({ item }) => <LedgerRow entry={item} />}
      ListHeaderComponent={header}
      contentContainerStyle={entries.length === 0 && styles.emptyWrap}
      ListEmptyComponent={
        !ledger.isLoading ? <Text style={styles.empty}>{t('history.empty')}</Text> : null
      }
      onEndReached={() => {
        if (ledger.hasNextPage && !ledger.isFetchingNextPage) void ledger.fetchNextPage();
      }}
      onEndReachedThreshold={0.5}
      refreshControl={
        <RefreshControl
          refreshing={ledger.isRefetching || me.isRefetching}
          onRefresh={() => {
            void me.refetch();
            void ledger.refetch();
          }}
        />
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  balanceCard: {
    backgroundColor: colors.primary,
    margin: spacing.md,
    borderRadius: 16,
    padding: spacing.lg,
  },
  balanceLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 13 },
  balanceValue: { color: '#fff', fontSize: 40, fontWeight: '800', marginTop: spacing.xs },
  available: { color: 'rgba(255,255,255,0.9)', fontSize: 14, marginTop: spacing.xs },
  scanButton: { marginHorizontal: spacing.md },
  sectionTitle: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
    marginHorizontal: spacing.md,
    textTransform: 'uppercase',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowLabel: { fontSize: 15, fontWeight: '600', color: colors.text },
  rowDate: { fontSize: 12, color: colors.muted, marginTop: 2 },
  amount: { fontSize: 17, fontWeight: '700' },
  emptyWrap: { flexGrow: 1 },
  empty: { color: colors.muted, fontSize: 15, textAlign: 'center', marginTop: spacing.xl },
});
