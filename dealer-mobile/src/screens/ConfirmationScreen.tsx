import React from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { RegisterOut } from '../api/types';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { StatusPill } from '../components/StatusPill';
import { dismiss, retry, type QueuedRegistration } from '../offline/queue';
import { useIsOnline } from '../offline/net';
import { useQueueItem } from '../offline/useQueue';
import type { MainStackScreenProps } from '../navigation/types';
import { colors, radius, spacing } from '../theme';
import { formatDate, formatPoints, STATUS_LABEL } from '../utils/format';
import { maskPhone } from '../utils/phone';

/** Why a sale that landed paid nothing. Silence here reads as a bug. */
function pointsNote(result: RegisterOut): string | null {
  if (result.points_awarded > 0) return null;
  switch (result.warranty.status) {
    case 'pending_backdate':
      return 'Points are paid once GoodBed approves the backdated invoice.';
    case 'pending_confirmation':
      return 'Points are paid once the customer confirms by SMS.';
    case 'pending_review':
      return 'Points are paid once GoodBed reviews this registration.';
    default:
      return result.idempotent ? 'Points for this sale were already paid.' : null;
  }
}

export function ConfirmationScreen({ route, navigation }: MainStackScreenProps<'Confirmation'>) {
  const { queueId } = route.params;
  const item = useQueueItem(queueId);
  const online = useIsOnline();

  const registerNext = () => navigation.popToTop();

  if (!item) {
    return (
      <ScreenBackground>
        <View style={styles.centre}>
          <Text style={styles.title}>This sale is no longer queued</Text>
          <Text style={styles.body}>Check the Sales tab to see where it ended up.</Text>
          <Button
            title="Register another"
            size="lg"
            onPress={registerNext}
            style={styles.action}
          />
        </View>
      </ScreenBackground>
    );
  }

  return (
    <ScreenBackground>
      <ScrollView contentContainerStyle={styles.content}>
        {item.status === 'sending' || (item.status === 'pending' && online && item.attempts === 0) ? (
          <Sending item={item} />
        ) : null}

        {item.status === 'pending' && !(online && item.attempts === 0) ? (
          <Queued item={item} online={online} />
        ) : null}

        {item.status === 'done' && item.result ? (
          <Registered result={item.result} />
        ) : null}

        {item.status === 'done' && !item.result ? <Recorded /> : null}

        {item.status === 'failed' ? (
          <Failed
            item={item}
            onFix={() =>
              navigation.replace('Register', { draft: item.body, retryOf: item.id })
            }
            onRetry={() => retry(item.id)}
            onDiscard={() => {
              dismiss(item.id);
              navigation.popToTop();
            }}
          />
        ) : null}

        {item.status !== 'failed' ? (
          <Button
            title="Register another"
            size="lg"
            onPress={registerNext}
            style={styles.action}
          />
        ) : null}
      </ScrollView>
    </ScreenBackground>
  );
}

function Sending({ item }: { item: QueuedRegistration }) {
  return (
    <View style={styles.centre}>
      <ActivityIndicator size="large" color={colors.primary} />
      <Text style={styles.title}>Registering the sale…</Text>
      <Text style={styles.body}>
        {item.body.customer_name} · invoice {item.body.invoice_ref}
      </Text>
    </View>
  );
}

function Queued({ item, online }: { item: QueuedRegistration; online: boolean }) {
  return (
    <View style={styles.centre}>
      <Text style={styles.icon}>📥</Text>
      <StatusPill label="Saved on this phone" tone="warning" />
      <Text style={styles.title}>The sale is safe</Text>
      <Text style={styles.body}>
        {online
          ? (item.lastError ?? 'Retrying now.')
          : 'There is no connection right now. This sale sends itself the moment you are back online — you do not need to do anything.'}
      </Text>
      <View style={styles.summary}>
        <Row label="Customer" value={item.body.customer_name} />
        <Row label="Mobile" value={maskPhone(item.body.customer_phone)} />
        <Row label="Invoice" value={item.body.invoice_ref} last />
      </View>
    </View>
  );
}

function Registered({ result }: { result: RegisterOut }) {
  const note = pointsNote(result);
  return (
    <View style={styles.centre}>
      <Text style={styles.icon}>✅</Text>
      <StatusPill
        label={result.idempotent ? 'Already saved earlier' : STATUS_LABEL[result.warranty.status]}
        tone={result.idempotent ? 'info' : 'success'}
      />
      <Text style={styles.title}>Warranty registered</Text>
      <Text style={styles.body}>{result.warranty.model_name ?? 'GoodBed mattress'}</Text>

      <View style={styles.hero}>
        <Text style={styles.heroLabel}>Warranty covers until</Text>
        <Text style={styles.heroValue}>{formatDate(result.warranty.warranty_end_date)}</Text>
        <Text style={styles.heroMeta}>
          {result.warranty.warranty_months} months from{' '}
          {formatDate(result.warranty.warranty_start_date)}
        </Text>
      </View>

      <View style={styles.pointsCard}>
        <Text style={styles.pointsValue}>
          {result.points_awarded > 0 ? `+${formatPoints(result.points_awarded)}` : '0'} points
        </Text>
        <Text style={styles.pointsBalance}>
          Balance {formatPoints(result.balance)} points
        </Text>
      </View>
      {note ? <Text style={styles.note}>{note}</Text> : null}

      <View style={styles.summary}>
        <Row label="Customer" value={result.customer.name} />
        <Row label="Mobile" value={maskPhone(result.customer.phone)} />
        <Row label="Invoice" value={result.warranty.invoice_ref ?? '—'} last />
      </View>
    </View>
  );
}

/**
 * A sale that landed but whose response this phone no longer holds.
 *
 * Only reachable for a sale registered by an older version of the app that is
 * still inside the queue's retention window. Blank is the one thing this screen
 * must never be: its entire job is to say whether the sale is safe.
 */
function Recorded() {
  return (
    <View style={styles.centre}>
      <Text style={styles.icon}>✅</Text>
      <StatusPill label="Registered" tone="success" />
      <Text style={styles.title}>This sale is registered</Text>
      <Text style={styles.body}>Open the Sales tab to see it with the rest.</Text>
    </View>
  );
}

function Failed({
  item,
  onFix,
  onRetry,
  onDiscard,
}: {
  item: QueuedRegistration;
  onFix: () => void;
  onRetry: () => void;
  onDiscard: () => void;
}) {
  // Everything the dealer can actually change on the form. A duplicate invoice
  // and a withdrawn product both belong here: one is a bill number they retype,
  // the other a product they re-pick. Anything else — a suspended dealership,
  // say — is not theirs to fix, and offering "fix details" would waste their time.
  const fixable =
    item.lastErrorCode === 'validation_error' ||
    item.lastErrorCode === 'duplicate_invoice' ||
    item.lastErrorCode === 'invalid_product' ||
    item.lastErrorCode === 'missing_product' ||
    item.lastErrorCode === 'idempotency_key_reused';

  return (
    <View style={styles.centre}>
      <Text style={styles.icon}>⚠️</Text>
      <StatusPill label="Not registered" tone="danger" />
      <Text style={styles.title}>GoodBed could not accept this sale</Text>
      <Text style={styles.body}>{item.lastError ?? 'The registration was rejected.'}</Text>

      <View style={styles.summary}>
        <Row label="Customer" value={item.body.customer_name} />
        <Row label="Mobile" value={maskPhone(item.body.customer_phone)} />
        <Row label="Invoice" value={item.body.invoice_ref} last />
      </View>

      {fixable ? (
        <Button title="Fix the details" size="lg" onPress={onFix} style={styles.action} />
      ) : (
        <Button title="Try again" size="lg" onPress={onRetry} style={styles.action} />
      )}
      <Button
        title="Discard this sale"
        variant="ghost"
        onPress={onDiscard}
        style={styles.secondary}
      />
    </View>
  );
}

function Row({ label, value, last = false }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.row, last && styles.rowLast]}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 2, flexGrow: 1 },
  centre: { alignItems: 'center', paddingTop: spacing.xl },
  icon: { fontSize: 44, marginBottom: spacing.sm },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: colors.text,
    marginTop: spacing.sm,
    textAlign: 'center',
    letterSpacing: -0.3,
  },
  body: {
    fontSize: 15,
    color: colors.muted,
    marginTop: spacing.xs,
    textAlign: 'center',
    lineHeight: 21,
  },
  hero: {
    alignSelf: 'stretch',
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    padding: spacing.lg,
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  heroLabel: { color: 'rgba(255,255,255,0.75)', fontSize: 13, fontWeight: '600' },
  heroValue: {
    color: '#fff',
    fontSize: 30,
    fontWeight: '800',
    marginTop: spacing.xs,
    letterSpacing: -0.5,
  },
  heroMeta: { color: 'rgba(255,255,255,0.75)', fontSize: 13, marginTop: spacing.xs },
  pointsCard: {
    alignSelf: 'stretch',
    backgroundColor: colors.accentSoft,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.sm,
    alignItems: 'center',
  },
  pointsValue: { fontSize: 22, fontWeight: '800', color: colors.primary },
  pointsBalance: { fontSize: 13, color: colors.muted, marginTop: 2 },
  note: {
    fontSize: 13,
    color: colors.muted,
    marginTop: spacing.md,
    textAlign: 'center',
    lineHeight: 19,
  },
  summary: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.md,
    marginTop: spacing.lg,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm + 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    gap: spacing.md,
  },
  rowLast: { borderBottomWidth: 0 },
  rowLabel: { fontSize: 14, color: colors.muted },
  rowValue: { flex: 1, fontSize: 14, fontWeight: '600', color: colors.text, textAlign: 'right' },
  action: { alignSelf: 'stretch', marginTop: spacing.xl },
  secondary: { alignSelf: 'stretch', marginTop: spacing.xs },
});
