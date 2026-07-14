import React from 'react';
import { FlatList, Image, StyleSheet, Text, View } from 'react-native';

import type { Reward } from '../api/rewards';
import type { Redemption } from '../api/types';
import { Button } from '../components/Button';
import { StatusPill } from '../components/StatusPill';
import { useMe } from '../hooks/useMe';
import { useCancelRedemption, useRedemptions } from '../hooks/useRedemptions';
import { useRedeemReward, useRewards } from '../hooks/useRewards';
import { useI18n } from '../i18n/I18nProvider';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';

function RewardCard({
  reward,
  available,
  loading,
  onRedeem,
}: {
  reward: Reward;
  available: number;
  loading: boolean;
  onRedeem: (id: string) => void;
}) {
  const { t } = useI18n();
  const affordable = available >= reward.points_cost;
  return (
    <View style={styles.card}>
      {reward.image_url ? (
        <Image source={{ uri: reward.image_url }} style={styles.image} resizeMode="cover" />
      ) : null}
      <Text style={styles.cardTitle}>{reward.title}</Text>
      {reward.description ? (
        <Text style={styles.cardDesc}>{reward.description}</Text>
      ) : null}
      <Text style={styles.cost}>{t('rewards.cost', { n: reward.points_cost })}</Text>
      {!affordable ? <Text style={styles.insufficient}>{t('rewards.insufficient')}</Text> : null}
      <Button
        title={t('rewards.redeem')}
        onPress={() => onRedeem(reward.id)}
        disabled={!affordable}
        loading={loading}
        style={{ marginTop: spacing.sm }}
      />
    </View>
  );
}

function RequestRow({ item, onCancel }: { item: Redemption; onCancel: (id: string) => void }) {
  const { t } = useI18n();
  return (
    <View style={styles.requestRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.requestPoints}>{item.points} pts</Text>
        <Text style={styles.requestDate}>{new Date(item.created_at).toLocaleString()}</Text>
      </View>
      <StatusPill status={item.status} label={t(`status.${item.status}`)} />
      {item.status === 'pending' && (
        <Text style={styles.cancel} onPress={() => onCancel(item.id)}>
          {t('redeem.cancel')}
        </Text>
      )}
    </View>
  );
}

export function RewardsScreen(_props: AppTabScreenProps<'Rewards'>) {
  const { t } = useI18n();
  const me = useMe();
  const rewards = useRewards();
  const redeem = useRedeemReward();
  const redemptions = useRedemptions();
  const cancel = useCancelRedemption();

  const available = me.data?.available ?? 0;

  const header = (
    <View>
      <View style={styles.balanceCard}>
        <Text style={styles.balanceLabel}>{t('redeem.available')}</Text>
        <Text style={styles.balanceValue}>{available} pts</Text>
      </View>
    </View>
  );

  const footer = (
    <View>
      <Text style={styles.heading}>{t('redeem.yourRequests')}</Text>
      {(redemptions.data ?? []).length === 0 && !redemptions.isLoading ? (
        <Text style={styles.empty}>{t('redeem.empty')}</Text>
      ) : (
        (redemptions.data ?? []).map((item) => (
          <RequestRow key={item.id} item={item} onCancel={(id) => cancel.mutate(id)} />
        ))
      )}
    </View>
  );

  return (
    <FlatList
      style={styles.container}
      data={rewards.data ?? []}
      keyExtractor={(r) => r.id}
      renderItem={({ item }) => (
        <RewardCard
          reward={item}
          available={available}
          loading={redeem.isPending && redeem.variables === item.id}
          onRedeem={(id) => redeem.mutate(id)}
        />
      )}
      contentContainerStyle={styles.content}
      ListHeaderComponent={header}
      ListFooterComponent={footer}
      ListEmptyComponent={
        !rewards.isLoading ? <Text style={styles.empty}>{t('rewards.empty')}</Text> : null
      }
      refreshing={rewards.isRefetching || redemptions.isRefetching || me.isRefetching}
      onRefresh={() => {
        void me.refetch();
        void rewards.refetch();
        void redemptions.refetch();
      }}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.md },
  balanceCard: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  balanceLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 13 },
  balanceValue: { color: '#fff', fontSize: 34, fontWeight: '800', marginTop: spacing.xs },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  image: {
    width: '100%',
    maxWidth: '100%',
    height: 140,
    borderRadius: 12,
    marginBottom: spacing.sm,
  },
  cardTitle: { fontSize: 17, fontWeight: '700', color: colors.text },
  cardDesc: { fontSize: 14, color: colors.muted, marginTop: spacing.xs },
  cost: { fontSize: 16, fontWeight: '700', color: colors.primary, marginTop: spacing.sm },
  insufficient: { fontSize: 13, color: colors.danger, marginTop: spacing.xs },
  heading: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  requestRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  requestPoints: { fontSize: 16, fontWeight: '600', color: colors.text },
  requestDate: { fontSize: 12, color: colors.muted, marginTop: 2 },
  cancel: { color: colors.danger, marginLeft: spacing.md, fontWeight: '600' },
  empty: { color: colors.muted, fontSize: 15, marginTop: spacing.md },
});
