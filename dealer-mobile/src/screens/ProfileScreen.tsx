import React from 'react';
import { Alert, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { OfflineBanner } from '../components/OfflineBanner';
import { ScreenBackground } from '../components/ScreenBackground';
import { StatusPill } from '../components/StatusPill';
import { usePointsSummary } from '../hooks/useDealerData';
import { useQueue } from '../offline/useQueue';
import { colors, radius, spacing } from '../theme';
import { formatPoints } from '../utils/format';
import { formatPhone } from '../utils/phone';

export function ProfileScreen() {
  const { staff, dealer, signOut } = useAuth();
  const summary = usePointsSummary();
  const { pendingCount, failedCount } = useQueue();

  const unsent = pendingCount + failedCount;

  const onSignOut = () => {
    // Queued sales only send while their own dealership is signed in. Signing
    // out on top of unsent work is how a real sale quietly goes missing.
    if (unsent > 0) {
      Alert.alert(
        'Unsent sales on this phone',
        `${unsent} ${unsent === 1 ? 'sale has' : 'sales have'} not reached GoodBed yet. They can only be sent while you are signed in with this shop's account.`,
        [
          { text: 'Stay signed in', style: 'cancel' },
          { text: 'Sign out anyway', style: 'destructive', onPress: () => void signOut() },
        ]
      );
      return;
    }
    Alert.alert('Sign out?', 'You will need your mobile number and a code to sign back in.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: () => void signOut() },
    ]);
  };

  return (
    <ScreenBackground>
      <OfflineBanner />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <Text style={styles.dealerName}>{dealer?.name ?? 'Your dealership'}</Text>
            {dealer ? <StatusPill label={`Code ${dealer.code}`} tone="info" /> : null}
          </View>
          <Text style={styles.cardMeta}>
            Points are earned by the shop, not by one person — anyone on this account can spend
            them.
          </Text>
          <View style={styles.pointsRow}>
            <View style={styles.pointsItem}>
              <Text style={styles.pointsValue}>
                {formatPoints(summary.data?.available ?? 0)}
              </Text>
              <Text style={styles.pointsLabel}>Available</Text>
            </View>
            <View style={styles.pointsItem}>
              <Text style={styles.pointsValue}>
                {formatPoints(summary.data?.total_earned ?? 0)}
              </Text>
              <Text style={styles.pointsLabel}>Earned all-time</Text>
            </View>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Signed in as</Text>
        <View style={styles.card}>
          <Field label="Name" value={staff?.name ?? '—'} />
          <Field label="Mobile" value={staff ? formatPhone(staff.phone) : '—'} />
          <Field
            label="Role"
            value={staff?.role === 'owner' ? 'Owner' : 'Counter staff'}
            last
          />
        </View>

        <Text style={styles.sectionTitle}>On this phone</Text>
        <View style={styles.card}>
          <Field label="Waiting to send" value={`${pendingCount}`} />
          <Field label="Needs attention" value={`${failedCount}`} last />
        </View>

        <Button
          title="Sign out"
          variant="secondary"
          onPress={onSignOut}
          style={styles.signOut}
        />
        <Text style={styles.footnote}>
          Accounts are created by GoodBed. To add another person at your counter, ask your
          GoodBed representative.
        </Text>
      </ScrollView>
    </ScreenBackground>
  );
}

function Field({ label, value, last = false }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.field, last && styles.fieldLast]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <Text style={styles.fieldValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl * 2 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  dealerName: { flex: 1, fontSize: 20, fontWeight: '800', color: colors.text },
  cardMeta: { fontSize: 13, color: colors.muted, marginTop: spacing.xs, lineHeight: 19 },
  pointsRow: { flexDirection: 'row', marginTop: spacing.md, gap: spacing.lg },
  pointsItem: { flex: 1 },
  pointsValue: { fontSize: 22, fontWeight: '800', color: colors.primary },
  pointsLabel: { fontSize: 12, color: colors.muted, marginTop: 2, fontWeight: '600' },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.muted,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  field: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm + 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: spacing.md,
  },
  fieldLast: { borderBottomWidth: 0 },
  fieldLabel: { fontSize: 14, color: colors.muted },
  fieldValue: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.text, textAlign: 'right' },
  signOut: { marginTop: spacing.xl },
  footnote: {
    fontSize: 12,
    color: colors.faint,
    marginTop: spacing.md,
    textAlign: 'center',
    lineHeight: 18,
  },
});
