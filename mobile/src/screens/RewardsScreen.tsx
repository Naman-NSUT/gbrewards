import Slider from '@react-native-community/slider';
import React, { useState } from 'react';
import { FlatList, Image, Pressable, StyleSheet, Text, View } from 'react-native';

import type { Reward } from '../api/rewards';
import type { Redemption } from '../api/types';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { StatusPill } from '../components/StatusPill';
import { useMe } from '../hooks/useMe';
import { useCancelRedemption, useRedemptions } from '../hooks/useRedemptions';
import { useRedeemReward, useRewards } from '../hooks/useRewards';
import { useI18n } from '../i18n/I18nProvider';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';
import { clampQuantity, maxRedeemableQuantity } from '../utils/redeem';

/**
 * One reward, with a slider for how many of it to take.
 *
 * Rewards are priced per unit — "Cash 500, 50 pts" — so a worker with 300 points
 * wants six, not six separate requests. The slider's ceiling is what the balance
 * can actually cover, which is also what the server will accept: the alternative
 * is offering a quantity and then refusing it.
 */
function RewardCard({
  reward,
  available,
  loading,
  onRedeem,
}: {
  reward: Reward;
  available: number;
  loading: boolean;
  onRedeem: (id: string, quantity: number) => void;
}) {
  const { t } = useI18n();
  const maxQuantity = maxRedeemableQuantity(available, reward.points_cost);
  const affordable = maxQuantity >= 1;
  const [quantity, setQuantity] = useState(1);
  const chosen = clampQuantity(quantity, maxQuantity);
  const total = reward.points_cost * chosen;

  return (
    <View style={styles.card}>
      {reward.image_url ? (
        <Image source={{ uri: reward.image_url }} style={styles.image} resizeMode="cover" />
      ) : null}
      <Text style={styles.cardTitle}>{reward.title}</Text>
      {reward.description ? <Text style={styles.cardDesc}>{reward.description}</Text> : null}
      <Text style={styles.cost}>{t('rewards.cost', { n: reward.points_cost })}</Text>

      {affordable && maxQuantity > 1 ? (
        <View style={styles.quantityBlock}>
          <View style={styles.quantityHeader}>
            <Text style={styles.quantityLabel}>{t('rewards.quantity')}</Text>
            <Text style={styles.quantityValue}>{chosen}</Text>
          </View>
          <View style={styles.sliderRow}>
            <Pressable
              style={styles.step}
              onPress={() => setQuantity(Math.max(1, chosen - 1))}
              disabled={chosen <= 1}
              accessibilityRole="button"
              accessibilityLabel={t('rewards.fewer')}
            >
              <Text style={[styles.stepText, chosen <= 1 && styles.stepDisabled]}>−</Text>
            </Pressable>
            <Slider
              style={styles.slider}
              minimumValue={1}
              maximumValue={maxQuantity}
              step={1}
              value={chosen}
              onValueChange={setQuantity}
              minimumTrackTintColor={colors.primary}
              maximumTrackTintColor={colors.border}
              thumbTintColor={colors.primary}
            />
            <Pressable
              style={styles.step}
              onPress={() => setQuantity(Math.min(maxQuantity, chosen + 1))}
              disabled={chosen >= maxQuantity}
              accessibilityRole="button"
              accessibilityLabel={t('rewards.more')}
            >
              <Text style={[styles.stepText, chosen >= maxQuantity && styles.stepDisabled]}>+</Text>
            </Pressable>
          </View>
          <Text style={styles.total}>
            {t('rewards.total', { q: chosen, title: reward.title, n: total })}
          </Text>
        </View>
      ) : null}

      {!affordable ? <Text style={styles.insufficient}>{t('rewards.insufficient')}</Text> : null}
      <Button
        title={
          affordable && chosen > 1 ? t('rewards.redeemMany', { q: chosen }) : t('rewards.redeem')
        }
        onPress={() => onRedeem(reward.id, chosen)}
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
        <Text style={styles.requestPoints}>
          {item.quantity > 1 ? `${item.quantity} × ` : ''}
          {item.points} pts
        </Text>
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
    <ScreenBackground>
      <FlatList
        style={styles.container}
        data={rewards.data ?? []}
      keyExtractor={(r) => r.id}
      renderItem={({ item }) => (
        <RewardCard
          reward={item}
          available={available}
          loading={redeem.isPending && redeem.variables?.rewardId === item.id}
          onRedeem={(rewardId, quantity) => redeem.mutate({ rewardId, quantity })}
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
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: 'transparent' },
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
  quantityBlock: {
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  quantityHeader: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  quantityLabel: { fontSize: 13, color: colors.muted, fontWeight: '600' },
  quantityValue: { fontSize: 20, fontWeight: '800', color: colors.text },
  sliderRow: { flexDirection: 'row', alignItems: 'center' },
  slider: { flex: 1, height: 40 },
  step: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepText: { fontSize: 20, fontWeight: '700', color: colors.primary, lineHeight: 24 },
  stepDisabled: { color: colors.faint },
  total: { fontSize: 14, fontWeight: '700', color: colors.primary, marginTop: spacing.xs },
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
