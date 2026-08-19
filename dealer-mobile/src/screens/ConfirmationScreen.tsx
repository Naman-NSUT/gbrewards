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
import { shortSerial } from '../utils/serial';

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

  const scanNext = () => navigation.popToTop();

  if (!item) {
    return (
      <ScreenBackground>
        <View style={styles.centre}>
          <Text style={styles.title}>This sale is no longer queued</Text>
          <Text style={styles.body}>Check the Sales tab to see where it ended up.</Text>
          <Button title="Scan next" size="lg" onPress={scanNext} style={styles.action} />
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

        {item.status === 'done' && !item.result ? (
          <AlreadyRegistered item={item} />
        ) : null}

        {item.status === 'failed' ? (
          <Failed
            item={item}
            onFix={() =>
              navigation.replace('CustomerDetails', {
                serial: item.body.serial,
                preview: null,
                draft: item.body,
                retryOf: item.id,
              })
            }
            onRetry={() => retry(item.id)}
            onDiscard={() => {
              dismiss(item.id);
              navigation.popToTop();
            }}
          />
        ) : null}

        {item.status !== 'failed' ? (
          <Button title="Scan next" size="lg" onPress={scanNext} style={styles.action} />
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
        {item.body.customer_name} · {shortSerial(item.body.serial)}
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
        <Row label="Invoice" value={item.body.invoice_ref} />
        <Row label="Serial" value={shortSerial(item.body.serial)} last />
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
        <Row label="Serial" value={shortSerial(result.warranty.serial)} />
        <Row label="Invoice" value={result.warranty.invoice_ref ?? '—'} last />
      </View>

      {result.unit_unverified ? (
        <Text style={styles.note}>
          GoodBed will confirm this unit&apos;s details shortly. The sale is recorded either way.
        </Text>
      ) : null}
    </View>
  );
}

function AlreadyRegistered({ item }: { item: QueuedRegistration }) {
  return (
    <View style={styles.centre}>
      <Text style={styles.icon}>ℹ️</Text>
      <StatusPill label="Already registered" tone="warning" />
      <Text style={styles.title}>This unit is already registered</Text>
      <Text style={styles.body}>
        {item.lastError ??
          'Another dealer has already registered this serial, so no new warranty was created.'}
      </Text>
      <Text style={styles.note}>
        If you believe this unit is yours, tell GoodBed the serial {shortSerial(item.body.serial)}.
      </Text>
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
  // A wrong phone number or a mistyped invoice is fixable; an unallocated unit
  // is not, and offering "fix details" for it would waste the dealer's time.
  const fixable =
    item.lastErrorCode === 'validation_error' ||
    item.lastErrorCode === 'invalid_serial' ||
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
        <Row label="Serial" value={shortSerial(item.body.serial)} last />
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
