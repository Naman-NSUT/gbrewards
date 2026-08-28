import React from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import type { WarrantyOut } from '../api/types';
import { BannerCarousel } from '../components/BannerCarousel';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { useAuth } from '../auth/AuthContext';
import { usePointsSummary, useRegistrations } from '../hooks/useDealerData';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

/** Newest first, and only the handful worth glancing at on a home screen. */
const RECENT_LIMIT = 8;

function SaleRow({ sale }: { sale: WarrantyOut }) {
  const registered = new Date(sale.registered_at);
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel} numberOfLines={1}>
          {sale.model_name ?? 'Mattress'}
        </Text>
        <Text style={styles.rowDate}>
          {sale.customer?.name ? `${sale.customer.name} · ` : ''}
          {registered.toLocaleDateString()}
        </Text>
      </View>
      <Text style={styles.months}>{sale.warranty_months} mo</Text>
    </View>
  );
}

export function HomeScreen({ navigation }: AppTabScreenProps<'Home'>) {
  const { staff, dealer } = useAuth();
  const points = usePointsSummary();
  const registrations = useRegistrations();

  const sales = (registrations.data ?? []).slice(0, RECENT_LIMIT);
  const firstName = staff?.name?.trim().split(/\s+/)[0];

  const header = (
    <View>
      {firstName ? (
        <View style={styles.greetingCard}>
          <Text style={styles.greeting} numberOfLines={1}>
            Hi {firstName}
          </Text>
          {/* The shop, not the person: a dealership can have several logins and
              the operator needs to know which books they are looking at. */}
          <Text style={styles.greetingSub} numberOfLines={1}>
            {dealer?.name ?? 'Your dealership'}
          </Text>
        </View>
      ) : null}

      <BannerCarousel />

      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>Points balance</Text>
        <Text style={styles.balanceValue}>{points.data?.balance ?? '—'} pts</Text>
        {points.data && points.data.available !== points.data.balance ? (
          // Pending redemptions are already spoken for. Showing only the balance
          // would have a dealer plan around points they cannot actually use.
          <Text style={styles.available}>{points.data.available} available to redeem</Text>
        ) : null}
      </View>

      <Button
        title="Scan a mattress"
        onPress={() => navigation.navigate('Scan')}
        style={styles.scanButton}
      />

      <Text style={styles.sectionTitle}>Recent sales</Text>
    </View>
  );

  return (
    <ScreenBackground>
      <FlatList
        style={styles.container}
        data={sales}
        keyExtractor={(s) => s.id}
        renderItem={({ item }) => <SaleRow sale={item} />}
        ListHeaderComponent={header}
        contentContainerStyle={sales.length === 0 ? styles.emptyWrap : undefined}
        ListEmptyComponent={
          !registrations.isLoading ? (
            <Text style={styles.empty}>No sales registered yet.</Text>
          ) : null
        }
        refreshControl={
          <RefreshControl
            refreshing={points.isRefetching || registrations.isRefetching}
            onRefresh={() => {
              void points.refetch();
              void registrations.refetch();
            }}
          />
        }
      />
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
  greetingCard: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  greeting: { fontSize: 24, fontWeight: '800', color: colors.text },
  greetingSub: { fontSize: 14, color: colors.muted, marginTop: 2 },
  balanceCard: {
    backgroundColor: colors.primary,
    margin: spacing.md,
    borderRadius: 16,
    padding: spacing.lg,
  },
  balanceLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 13 },
  balanceValue: { color: colors.onPrimary, fontSize: 40, fontWeight: '800', marginTop: spacing.xs },
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
  months: { fontSize: 15, fontWeight: '700', color: colors.accent },
  emptyWrap: { flexGrow: 1 },
  empty: { color: colors.muted, fontSize: 15, textAlign: 'center', marginTop: spacing.xl },
});
