import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { signup } from '../api/auth';
import { ApiRequestError } from '../api/client';
import { Button } from '../components/Button';
import { ScreenBackground } from '../components/ScreenBackground';
import { TextField } from '../components/TextField';
import type { AuthStackScreenProps } from '../navigation/types';
import { colors, spacing } from '../theme';
import { isValidPhone, normalisePhone } from '../utils/phone';

/**
 * A shop creates its own account.
 *
 * Only four things are required — a person, a shop, a number, a city. Everything
 * else can be filled in later from the admin side. A dealer stands at a counter
 * with a customer waiting; a long form here is a shop that never signs up.
 */
export function SignupScreen({ navigation }: AuthStackScreenProps<'Signup'>) {
  const [name, setName] = useState('');
  const [shopName, setShopName] = useState('');
  const [phone, setPhone] = useState('');
  const [city, setCity] = useState('');
  const [gst, setGst] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready =
    name.trim().length > 1 && shopName.trim().length > 1 && isValidPhone(phone);

  const submit = async () => {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      await signup({
        phone: (normalisePhone(phone) ?? phone),
        name: name.trim(),
        shop_name: shopName.trim(),
        city: city.trim() || undefined,
        gst_number: gst.trim() || undefined,
      });
      navigation.navigate('Otp', { phone: (normalisePhone(phone) ?? phone), isNewAccount: true });
    } catch (e) {
      if (e instanceof ApiRequestError && e.code === 'already_registered') {
        // Not an error the shop can fix by editing the form — send them to the
        // door they actually need.
        setError('This number already has an account. Go back and sign in instead.');
      } else {
        setError(
          e instanceof ApiRequestError ? e.message : 'Could not start signup. Try again.',
        );
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScreenBackground>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.body}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.title}>Create your shop account</Text>
          <Text style={styles.subtitle}>
            Register warranties for your customers and earn points on every sale.
          </Text>

          <TextField
            label="Your name"
            value={name}
            onChangeText={setName}
            autoCapitalize="words"
            placeholder="Ravi Mehta"
          />
          <TextField
            label="Shop name"
            value={shopName}
            onChangeText={setShopName}
            autoCapitalize="words"
            placeholder="Sunrise Beds"
          />
          <TextField
            label="Mobile number"
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
            placeholder="98765 43210"
            hint="You will sign in with this number"
          />
          <TextField
            label="City"
            value={city}
            onChangeText={setCity}
            autoCapitalize="words"
            placeholder="Nagpur"
          />
          <TextField
            label="GST number (optional)"
            value={gst}
            onChangeText={setGst}
            autoCapitalize="characters"
            placeholder="27AAAAA0000A1Z5"
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Button title="Send code" onPress={submit} disabled={!ready} loading={busy} />

          <Text style={styles.note}>
            You can start registering sales straight away. Redeeming points opens once
            GoodBed has verified your shop.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </ScreenBackground>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  body: { padding: spacing.lg, paddingBottom: spacing.xl, gap: spacing.sm },
  title: { fontSize: 24, fontWeight: '700', color: colors.text },
  subtitle: {
    fontSize: 14,
    color: colors.muted,
    marginBottom: spacing.md,
    lineHeight: 20,
  },
  error: { color: colors.danger, fontSize: 13.5, marginTop: spacing.xs },
  note: {
    fontSize: 12.5,
    color: colors.faint,
    marginTop: spacing.md,
    lineHeight: 18,
    textAlign: 'center',
  },
});
