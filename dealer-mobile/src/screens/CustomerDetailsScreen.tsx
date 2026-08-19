import React, { useMemo, useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import type { RegisterBody } from '../api/types';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { StatusPill } from '../components/StatusPill';
import { TextField } from '../components/TextField';
import { enqueue, replace } from '../offline/queue';
import type { MainStackScreenProps } from '../navigation/types';
import { colors, radius, spacing } from '../theme';
import { formatDateInput, parseDateInput, todayIso } from '../utils/format';
import { digitsOf, normalisePhone } from '../utils/phone';
import { shortSerial } from '../utils/serial';

/** Mirrors the server's BACKDATE_GRACE_DAYS default. Used only to warn the
 *  dealer early — the server decides, and disagreement costs a warning, not a
 *  wrong record. */
const BACKDATE_GRACE_DAYS_HINT = 7;

function isoToInput(iso: string | null | undefined): string {
  if (!iso) return '';
  const [year, month, day] = iso.slice(0, 10).split('-');
  if (!year || !month || !day) return '';
  return `${day}/${month}/${year}`;
}

function daysBefore(today: string, iso: string): number {
  const a = new Date(`${today}T00:00:00`);
  const b = new Date(`${iso}T00:00:00`);
  return Math.round((a.getTime() - b.getTime()) / 86_400_000);
}

export function CustomerDetailsScreen({
  route,
  navigation,
}: MainStackScreenProps<'CustomerDetails'>) {
  const { serial, preview, draft, retryOf } = route.params;

  const [name, setName] = useState(draft?.customer_name ?? '');
  const [phone, setPhone] = useState(digitsOf(draft?.customer_phone ?? '').slice(-10));
  const [invoiceRef, setInvoiceRef] = useState(draft?.invoice_ref ?? '');
  const [invoiceDate, setInvoiceDate] = useState(isoToInput(draft?.invoice_date));
  const [address, setAddress] = useState(draft?.customer_address ?? '');
  const [showErrors, setShowErrors] = useState(false);

  const phoneRef = useRef<TextInput>(null);
  const invoiceRefField = useRef<TextInput>(null);

  const errors = useMemo(() => {
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = "Enter the customer's name.";
    if (!normalisePhone(phone)) next.phone = 'Enter a valid 10-digit mobile number.';
    if (!invoiceRef.trim()) next.invoiceRef = 'Enter the invoice or bill number.';
    if (invoiceDate.trim() && !parseDateInput(invoiceDate)) {
      next.invoiceDate = 'Use DD/MM/YYYY.';
    }
    return next;
  }, [name, phone, invoiceRef, invoiceDate]);

  const parsedDate = parseDateInput(invoiceDate);
  const today = todayIso();
  const dateNotice = useMemo(() => {
    if (!parsedDate) return null;
    if (parsedDate > today) {
      return 'That date is in the future — the warranty will start today instead.';
    }
    const age = daysBefore(today, parsedDate);
    if (age > BACKDATE_GRACE_DAYS_HINT) {
      return 'That invoice is more than a week old, so GoodBed will review it before points are paid.';
    }
    return null;
  }, [parsedDate, today]);

  const onSubmit = () => {
    setShowErrors(true);
    if (Object.keys(errors).length > 0) return;

    const normalisedPhone = normalisePhone(phone);
    if (!normalisedPhone) return;

    const body: RegisterBody = {
      // The RAW scanned value: the backend owns the QR payload format and
      // normalises it. A client that pre-parses it breaks silently the day that
      // format changes.
      serial,
      customer_name: name.trim(),
      customer_phone: normalisedPhone,
      invoice_ref: invoiceRef.trim(),
      invoice_date: parsedDate,
      customer_address: address.trim() || null,
    };

    // Corrections get a NEW idempotency key: the same key with a different body
    // is rejected by the backend, and rightly so.
    const queueId = retryOf ? replace(retryOf, body) : enqueue(body);
    navigation.replace('Confirmation', { queueId });
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.unitCard}>
            <View style={styles.unitHeader}>
              <Text style={styles.unitModel} numberOfLines={1}>
                {preview?.model_name ?? 'GoodBed mattress'}
              </Text>
              <StatusPill
                label={preview ? `${preview.warranty_months} months` : 'Not checked'}
                tone={preview ? 'info' : 'warning'}
              />
            </View>
            <Text style={styles.unitSerial}>{shortSerial(serial)}</Text>
          </View>

          <TextField
            label="Customer name"
            value={name}
            onChangeText={setName}
            placeholder="Full name"
            autoCapitalize="words"
            returnKeyType="next"
            onSubmitEditing={() => phoneRef.current?.focus()}
            error={showErrors ? errors.name : null}
          />

          <TextField
            label="Customer mobile"
            value={phone}
            onChangeText={(value) => setPhone(digitsOf(value).slice(0, 10))}
            placeholder="98765 43210"
            keyboardType="number-pad"
            autoCapitalize="none"
            maxLength={10}
            inputRef={phoneRef}
            returnKeyType="next"
            onSubmitEditing={() => invoiceRefField.current?.focus()}
            error={showErrors ? errors.phone : null}
            hint="The warranty SMS goes to this number."
          />

          <TextField
            label="Invoice number"
            value={invoiceRef}
            onChangeText={setInvoiceRef}
            placeholder="e.g. INV-2043"
            autoCapitalize="characters"
            inputRef={invoiceRefField}
            returnKeyType="next"
            error={showErrors ? errors.invoiceRef : null}
          />

          <TextField
            label="Invoice date"
            optional
            value={invoiceDate}
            onChangeText={(value) => setInvoiceDate(formatDateInput(value))}
            placeholder="DD/MM/YYYY"
            keyboardType="number-pad"
            maxLength={10}
            error={showErrors ? errors.invoiceDate : null}
            hint="Leave blank if you are billing today."
          />

          {dateNotice ? (
            <View style={styles.notice}>
              <Text style={styles.noticeText}>{dateNotice}</Text>
            </View>
          ) : null}

          <TextField
            label="Delivery address"
            optional
            value={address}
            onChangeText={setAddress}
            placeholder="House, street, area"
            multiline
          />

          <Button
            title="Register sale"
            size="lg"
            onPress={onSubmit}
            style={styles.submit}
          />
          <Text style={styles.footnote}>
            Saved on this phone the moment you tap. If the connection drops, it is sent
            automatically — the sale is never lost.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 2 },
  unitCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
  },
  unitHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  unitModel: { flex: 1, fontSize: 17, fontWeight: '700', color: colors.text },
  unitSerial: { fontSize: 12, color: colors.muted, marginTop: spacing.xs, letterSpacing: 0.6 },
  notice: {
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: 'rgba(192,138,46,0.14)',
  },
  noticeText: { fontSize: 13, color: colors.text, lineHeight: 19 },
  submit: { marginTop: spacing.xl },
  footnote: {
    fontSize: 12,
    color: colors.muted,
    textAlign: 'center',
    marginTop: spacing.md,
    lineHeight: 18,
  },
});
