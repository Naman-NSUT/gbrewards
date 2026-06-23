import React, { useState } from 'react';
import { FlatList, StyleSheet, Text, TextInput, View } from 'react-native';

import { extractApiError } from '../api/client';
import type { Redemption, RedemptionStatus } from '../api/types';
import { Button } from '../components/Button';
import { useMe } from '../hooks/useMe';
import {
  useCancelRedemption,
  useCreateRedemption,
  useRedemptions,
} from '../hooks/useRedemptions';
import { useI18n } from '../i18n/I18nProvider';
import { colors, spacing } from '../theme';

const STATUS_COLOR: Record<RedemptionStatus, string> = {
  pending: colors.warning,
  approved: colors.primary,
  fulfilled: colors.success,
  rejected: colors.danger,
  cancelled: colors.muted,
};

function StatusPill({ status, label }: { status: RedemptionStatus; label: string }) {
  return (
    <View style={[styles.pill, { backgroundColor: STATUS_COLOR[status] }]}>
      <Text style={styles.pillText}>{label}</Text>
    </View>
  );
}

function RequestRow({ item, onCancel }: { item: Redemption; onCancel: (id: string) => void }) {
  const { t } = useI18n();
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>
        <Text style={styles.points}>{item.points} pts</Text>
        <Text style={styles.date}>{new Date(item.created_at).toLocaleString()}</Text>
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

export function RedeemScreen() {
  const { t } = useI18n();
  const me = useMe();
  const redemptions = useRedemptions();
  const create = useCreateRedemption();
  const cancel = useCancelRedemption();
  const [amount, setAmount] = useState('');
  const [error, setError] = useState<string | null>(null);

  const available = me.data?.available ?? 0;
  const points = parseInt(amount, 10);
  const valid = Number.isInteger(points) && points > 0 && points <= available;

  const onSubmit = () => {
    setError(null);
    if (!valid) {
      setError(t('redeem.errRange', { max: available }));
      return;
    }
    create.mutate(points, {
      onSuccess: () => setAmount(''),
      onError: (e) => {
        const api = extractApiError(e);
        setError(api?.message ?? t('redeem.errSubmit'));
      },
    });
  };

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.cardLabel}>{t('redeem.available')}</Text>
        <Text style={styles.cardValue}>{available} pts</Text>
      </View>

      <TextInput
        style={styles.input}
        placeholder={t('redeem.amount')}
        placeholderTextColor={colors.faint}
        value={amount}
        onChangeText={setAmount}
        keyboardType="number-pad"
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Button
        title={t('redeem.request')}
        onPress={onSubmit}
        loading={create.isPending}
        disabled={!valid}
        style={{ marginTop: spacing.sm }}
      />

      <Text style={styles.heading}>{t('redeem.yourRequests')}</Text>
      <FlatList
        data={redemptions.data ?? []}
        keyExtractor={(r) => r.id}
        renderItem={({ item }) => <RequestRow item={item} onCancel={(id) => cancel.mutate(id)} />}
        ListEmptyComponent={
          !redemptions.isLoading ? <Text style={styles.empty}>{t('redeem.empty')}</Text> : null
        }
        refreshing={redemptions.isRefetching}
        onRefresh={() => void redemptions.refetch()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: spacing.md },
  card: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  cardLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 13 },
  cardValue: { color: '#fff', fontSize: 34, fontWeight: '800', marginTop: spacing.xs },
  input: {
    height: 50,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    fontSize: 16,
    color: colors.text,
  },
  error: { color: colors.danger, marginTop: spacing.sm },
  heading: { fontSize: 18, fontWeight: '700', color: colors.text, marginTop: spacing.lg, marginBottom: spacing.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  points: { fontSize: 16, fontWeight: '600', color: colors.text },
  date: { fontSize: 12, color: colors.muted, marginTop: 2 },
  pill: { borderRadius: 12, paddingHorizontal: spacing.sm, paddingVertical: 2, marginLeft: spacing.sm },
  pillText: { color: '#fff', fontSize: 12, fontWeight: '600' },
  cancel: { color: colors.danger, marginLeft: spacing.md, fontWeight: '600' },
  empty: { color: colors.muted, fontSize: 15, marginTop: spacing.md },
});
