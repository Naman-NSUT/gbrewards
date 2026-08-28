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

import { errorMessage } from '../api/client';
import type { RegisterBody } from '../api/types';
import { Button } from '../components/Button';
import { OfflineBanner } from '../components/OfflineBanner';
import { ProductPicker } from '../components/ProductPicker';
import { ScreenBackground } from '../components/ScreenBackground';
import { TextField } from '../components/TextField';
import { useProducts } from '../hooks/useDealerData';
import { enqueue, replace } from '../offline/queue';
import type { MainStackScreenProps } from '../navigation/types';
import { colors, radius, spacing } from '../theme';
import { formatDateInput, parseDateInput, todayIso } from '../utils/format';
import { digitsOf, normalisePhone } from '../utils/phone';

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

/**
 * The whole registration flow, on one screen.
 *
 * There is nothing to scan any more, so this form is the entire product: the
 * dealer says what was sold, who bought it, and which bill it was on. It is
 * reached from Home in one tap and submits to the offline queue, never straight
 * to the network — the sale is recorded on this phone before anything else.
 */
export function RegisterScreen({ route, navigation }: MainStackScreenProps<'Register'>) {
  // A correction arrives with the rejected body; a fresh sale arrives with nothing.
  const draft = route.params?.draft;
  const retryOf = route.params?.retryOf;

  const products = useProducts();

  // `?? null` and not just `draft?.product_id`: a sale queued by the version that
  // scanned labels has a `serial` and no product, and lands here to be given one.
  const [productId, setProductId] = useState<string | null>(draft?.product_id ?? null);
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
    if (!productId) next.product = 'Choose the product you sold.';
    if (!name.trim()) next.name = "Enter the customer's name.";
    if (!normalisePhone(phone)) next.phone = 'Enter a valid 10-digit mobile number.';
    if (!invoiceRef.trim()) next.invoiceRef = 'Enter the invoice or bill number.';
    if (invoiceDate.trim() && !parseDateInput(invoiceDate)) {
      next.invoiceDate = 'Use DD/MM/YYYY.';
    }
    return next;
  }, [productId, name, phone, invoiceRef, invoiceDate]);

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
    if (!normalisedPhone || !productId) return;

    const body: RegisterBody = {
      product_id: productId,
      customer_name: name.trim(),
      customer_phone: normalisedPhone,
      // Trimmed to match the server, which strips before comparing: a trailing
      // space would otherwise slip past the one-warranty-per-invoice rule and be
      // a second, paid copy of the same sale.
      invoice_ref: invoiceRef.trim(),
      invoice_date: parsedDate,
      customer_address: address.trim() || null,
    };

    // Corrections get a NEW idempotency key: the same key with a different body
    // is rejected by the backend, and rightly so.
    const queueId = retryOf ? replace(retryOf, body) : enqueue(body);
    navigation.replace('Confirmation', { queueId });
  };

  const catalogue = products.data ?? [];
  // Only a hard failure — no list from the server AND nothing cached on this
  // phone — is worth a message. `listProducts` falls back to the cache silently.
  const loadError =
    products.isError && catalogue.length === 0
      ? errorMessage(products.error, 'Could not load your product list.')
      : null;

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
      >
        <OfflineBanner />
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <ProductPicker
            products={catalogue}
            value={productId}
            onChange={setProductId}
            loading={products.isLoading}
            loadError={loadError}
            onRetry={() => void products.refetch()}
            error={showErrors ? errors.product : null}
          />

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
            hint="One sale per bill — this is how GoodBed tells two sales apart."
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

          <Button title="Register warranty" size="lg" onPress={onSubmit} style={styles.submit} />
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
