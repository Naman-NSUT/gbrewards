import React from 'react';
import { Alert, FlatList, Image, Pressable, StyleSheet, Text, View } from 'react-native';

import { errorMessage } from '../api/client';
import type { RedemptionOut, RewardOut } from '../api/types';
import { Button } from '../components/Button';
import { EmptyState } from '../components/EmptyState';
import { OfflineBanner } from '../components/OfflineBanner';
import { redemptionTone, StatusPill } from '../components/StatusPill';
import { ScreenBackground } from '../components/ScreenBackground';
import {
  useCancelRedemption,
  usePointsSummary,
  useRedeemReward,
  useRedemptions,
  useRewards,
} from '../hooks/useDealerData';
import { colors, radius, spacing } from '../theme';
import { formatDateTime, formatPoints } from '../utils/format';

const REDEMPTION_LABEL: Record<RedemptionOut['status'], string> = {
  pending: 'Awaiting approval',
  approved: 'Approved',
  rejected: 'Rejected',
  fulfilled: 'Delivered',
  cancelled: 'Cancelled',
};

export function RewardsScreen() {
  const summary = usePointsSummary();
  const rewards = useRewards();
  const redemptions = useRedemptions();
  const redeem = useRedeemReward();
  const cancel = useCancelRedemption();

  // From the catalogue response, not the separate points call: it is the exact
  // balance each reward's `affordable` flag was measured against, so the button
  // and the number above it can never disagree.
  const catalogue = rewards.data;
  const available = catalogue?.available ?? summary.data?.available ?? 0;

  const onRedeem = (reward: RewardOut) => {
    Alert.alert(
      'Redeem this reward?',
      `${reward.name} costs ${formatPoints(reward.points_cost)} points. GoodBed will review the request.`,
      [
        { text: 'Not now', style: 'cancel' },
        {
          text: 'Redeem',
          onPress: () =>
            redeem.mutate(reward.id, {
              onError: (error) =>
                Alert.alert('Could not redeem', errorMessage(error, 'Please try again.')),
            }),
        },
      ]
    );
  };

  const onCancel = (redemption: RedemptionOut) => {
    Alert.alert('Cancel this request?', 'The points go back to your available balance.', [
      { text: 'Keep it', style: 'cancel' },
      {
        text: 'Cancel request',
        style: 'destructive',
        onPress: () =>
          cancel.mutate(redemption.id, {
            onError: (error) =>
              Alert.alert('Could not cancel', errorMessage(error, 'Please try again.')),
          }),
      },
    ]);
  };

  return (
    <ScreenBackground>
      <OfflineBanner />
      <FlatList
        data={catalogue?.items ?? []}
        keyExtractor={(reward) => reward.id}
        contentContainerStyle={styles.content}
        refreshing={rewards.isRefetching || redemptions.isRefetching || summary.isRefetching}
        onRefresh={() => {
          void summary.refetch();
          void rewards.refetch();
          void redemptions.refetch();
        }}
        ListHeaderComponent={
          <View style={styles.balanceCard}>
            <Text style={styles.balanceLabel}>Available to spend</Text>
            <Text style={styles.balanceValue}>{formatPoints(available)} points</Text>
          </View>
        }
        renderItem={({ item }) => (
          <RewardCard
            reward={item}
            loading={redeem.isPending && redeem.variables === item.id}
            onRedeem={() => onRedeem(item)}
          />
        )}
        ListEmptyComponent={
          !rewards.isLoading ? (
            <EmptyState
              icon="🎁"
              title="No rewards yet"
              body="GoodBed has not published a rewards catalogue. Your points keep accruing in the meantime."
            />
          ) : null
        }
        ListFooterComponent={
          <View>
            <Text style={styles.sectionTitle}>Your requests</Text>
            {(redemptions.data ?? []).length === 0 && !redemptions.isLoading ? (
              <Text style={styles.empty}>You have not redeemed anything yet.</Text>
            ) : (
              (redemptions.data ?? []).map((item) => (
                <RedemptionRow key={item.id} redemption={item} onCancel={() => onCancel(item)} />
              ))
            )}
          </View>
        }
      />
    </ScreenBackground>
  );
}

function RewardCard({
  reward,
  loading,
  onRedeem,
}: {
  reward: RewardOut;
  loading: boolean;
  onRedeem: () => void;
}) {
  // All three come from the server. It measures affordability against the
  // balance minus points already held by pending requests — recomputing from a
  // raw balance here would offer a Redeem button the server then refuses.
  const affordable = reward.affordable;
  const outOfStock = !reward.in_stock;
  const shortfall = reward.short_by;

  return (
    <View style={styles.card}>
      {reward.image_url ? (
        <Image source={{ uri: reward.image_url }} style={styles.image} resizeMode="cover" />
      ) : null}
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>{reward.name}</Text>
        {outOfStock ? <StatusPill label="Out of stock" tone="neutral" /> : null}
      </View>
      {reward.description ? <Text style={styles.cardBody}>{reward.description}</Text> : null}
      <Text style={styles.cost}>{formatPoints(reward.points_cost)} points</Text>
      {!affordable && !outOfStock ? (
        <Text style={styles.shortfall}>{formatPoints(shortfall)} points to go</Text>
      ) : null}
      <Button
        title={outOfStock ? 'Out of stock' : 'Redeem'}
        onPress={onRedeem}
        disabled={!affordable || outOfStock}
        loading={loading}
        style={styles.cardAction}
      />
    </View>
  );
}

function RedemptionRow({
  redemption,
  onCancel,
}: {
  redemption: RedemptionOut;
  onCancel: () => void;
}) {
  return (
    <View style={styles.requestRow}>
      <View style={styles.requestMain}>
        <Text style={styles.requestTitle}>{redemption.reward_name ?? 'Reward'}</Text>
        <Text style={styles.requestMeta}>
          {formatPoints(redemption.points)} points · {formatDateTime(redemption.created_at)}
        </Text>
        {redemption.note ? <Text style={styles.requestMeta}>{redemption.note}</Text> : null}
      </View>
      <View style={styles.requestSide}>
        <StatusPill
          label={REDEMPTION_LABEL[redemption.status]}
          tone={redemptionTone(redemption.status)}
        />
        {redemption.status === 'pending' ? (
          <Pressable onPress={onCancel} hitSlop={8}>
            <Text style={styles.cancel}>Cancel</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl * 2 },
  balanceCard: {
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  balanceLabel: { color: 'rgba(255,255,255,0.75)', fontSize: 13, fontWeight: '600' },
  balanceValue: {
    color: '#fff',
    fontSize: 30,
    fontWeight: '800',
    marginTop: spacing.xs,
    letterSpacing: -0.5,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  image: { width: '100%', height: 140, borderRadius: radius.sm, marginBottom: spacing.sm },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  cardTitle: { flex: 1, fontSize: 17, fontWeight: '700', color: colors.text },
  cardBody: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, lineHeight: 20 },
  cost: { fontSize: 16, fontWeight: '800', color: colors.primary, marginTop: spacing.sm },
  shortfall: { fontSize: 13, color: colors.warning, marginTop: 2 },
  cardAction: { marginTop: spacing.md },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  empty: { fontSize: 14, color: colors.muted },
  requestRow: {
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
  requestMain: { flex: 1 },
  requestSide: { alignItems: 'flex-end', gap: spacing.xs },
  requestTitle: { fontSize: 15, fontWeight: '700', color: colors.text },
  requestMeta: { fontSize: 13, color: colors.muted, marginTop: 2 },
  cancel: { fontSize: 13, fontWeight: '600', color: colors.danger },
});
