import { useFocusEffect } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useCallback, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { errorCode, errorMessage } from '../api/client';
import type { UnitPreviewOut } from '../api/types';
import { Button } from '../components/Button';
import { OfflineBanner } from '../components/OfflineBanner';
import { ScanResultSheet, type ScanOutcome } from '../components/ScanResultSheet';
import { ScreenBackground } from '../components/ScreenBackground';
import { TextField } from '../components/TextField';
import { usePreviewUnit } from '../hooks/useDealerData';
import type { AppTabScreenProps } from '../navigation/types';
import { colors, radius, spacing } from '../theme';
import { normaliseSerial } from '../utils/serial';

export function ScanScreen({ navigation }: AppTabScreenProps<'Scan'>) {
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const [outcome, setOutcome] = useState<ScanOutcome>(null);
  const [torch, setTorch] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualSerial, setManualSerial] = useState('');
  const [active, setActive] = useState(false);
  const preview = usePreviewUnit();

  // A QR sits in frame for many frames; without this the preview fires dozens of
  // times for one label.
  const lockedRef = useRef(false);

  // The camera is torn down when the dealer leaves this tab: a live preview
  // behind another screen drains a shop phone and, on Android, can hold the
  // camera against the next screen that wants it.
  useFocusEffect(
    useCallback(() => {
      setActive(true);
      lockedRef.current = false;
      setOutcome(null);
      return () => {
        setActive(false);
        setTorch(false);
      };
    }, [])
  );

  const check = (raw: string) => {
    const serial = normaliseSerial(raw);
    if (!serial) {
      lockedRef.current = false;
      return;
    }
    setOutcome({ kind: 'checking', serial });
    preview.mutate(serial, {
      onSuccess: (result) => setOutcome({ kind: 'preview', serial, preview: result }),
      onError: (error) => {
        const code = errorCode(error);
        // Could not ask. The allocation gate still runs server-side when the
        // registration is submitted, so blocking the sale here would cost a real
        // sale to protect against nothing.
        if (code === 'network_error' || code === 'timeout' || code === 'rate_limit_unavailable') {
          setOutcome({
            kind: 'unchecked',
            serial,
            message:
              "We couldn't check this unit right now. You can still take the customer's details — the sale is saved on this phone and sent as soon as you're back online.",
          });
          return;
        }
        setOutcome({
          kind: 'error',
          serial,
          title: "Couldn't check this unit",
          message: errorMessage(error, 'Please try scanning again.'),
        });
      },
    });
  };

  const onScanned = ({ data }: { data: string }) => {
    if (lockedRef.current) return;
    lockedRef.current = true;
    check(data);
  };

  const dismiss = () => {
    setOutcome(null);
    lockedRef.current = false;
  };

  const onContinue = (serial: string, unitPreview: UnitPreviewOut | null) => {
    setOutcome(null);
    lockedRef.current = false;
    navigation.navigate('CustomerDetails', { serial, preview: unitPreview });
  };

  const submitManual = () => {
    const value = manualSerial.trim();
    if (!value) return;
    setManualOpen(false);
    setManualSerial('');
    lockedRef.current = true;
    check(value);
  };

  if (!permission) {
    return <ScreenBackground />;
  }

  if (!permission.granted) {
    return (
      <ScreenBackground>
        <View style={[styles.permission, { paddingTop: insets.top + spacing.xl }]}>
          <Text style={styles.permIcon}>📷</Text>
          <Text style={styles.permTitle}>Allow the camera</Text>
          <Text style={styles.permBody}>
            The camera reads the QR code on the mattress label. Nothing is recorded until you
            enter the customer&apos;s details.
          </Text>
          <Button title="Allow camera" size="lg" onPress={requestPermission} style={styles.permAction} />
          <Button
            title="Type the serial instead"
            variant="secondary"
            onPress={() => setManualOpen(true)}
            style={styles.permSecondary}
          />
        </View>
        <ManualEntry
          visible={manualOpen}
          value={manualSerial}
          onChange={setManualSerial}
          onCancel={() => setManualOpen(false)}
          onSubmit={submitManual}
        />
        <ScanResultSheet outcome={outcome} onDismiss={dismiss} onContinue={onContinue} />
      </ScreenBackground>
    );
  }

  return (
    <View style={styles.root}>
      {active ? (
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          enableTorch={torch}
          barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
          onBarcodeScanned={outcome ? undefined : onScanned}
        />
      ) : null}

      <View style={[styles.topBar, { paddingTop: insets.top }]}>
        <OfflineBanner onPress={() => navigation.navigate('Tabs', { screen: 'Registrations' })} />
      </View>

      <View style={styles.overlay} pointerEvents="box-none">
        <View style={styles.frame} pointerEvents="none">
          <View style={[styles.corner, styles.cornerTl]} />
          <View style={[styles.corner, styles.cornerTr]} />
          <View style={[styles.corner, styles.cornerBl]} />
          <View style={[styles.corner, styles.cornerBr]} />
        </View>
        <Text style={styles.hint} pointerEvents="none">
          Point at the QR code on the mattress label
        </Text>
      </View>

      <View style={[styles.controls, { paddingBottom: insets.bottom + spacing.md }]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={torch ? 'Turn torch off' : 'Turn torch on'}
          onPress={() => setTorch((on) => !on)}
          style={[styles.controlButton, torch && styles.controlButtonOn]}
        >
          <Text style={styles.controlIcon}>{torch ? '🔦' : '💡'}</Text>
          <Text style={[styles.controlLabel, torch && styles.controlLabelOn]}>Torch</Text>
        </Pressable>

        {/* Labels get scuffed, wrapped, or printed badly. The serial is printed
            under the QR for exactly this reason, so typing it is a first-class
            path, not a hidden fallback. */}
        <Pressable
          accessibilityRole="button"
          onPress={() => setManualOpen(true)}
          style={styles.manualButton}
        >
          <Text style={styles.manualText}>Enter serial manually</Text>
        </Pressable>
      </View>

      <ManualEntry
        visible={manualOpen}
        value={manualSerial}
        onChange={setManualSerial}
        onCancel={() => setManualOpen(false)}
        onSubmit={submitManual}
      />
      <ScanResultSheet outcome={outcome} onDismiss={dismiss} onContinue={onContinue} />
    </View>
  );
}

function ManualEntry({
  visible,
  value,
  onChange,
  onCancel,
  onSubmit,
}: {
  visible: boolean;
  value: string;
  onChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Enter the serial</Text>
          <Text style={styles.modalBody}>
            It is printed in text under the QR code on the label.
          </Text>
          <TextField
            label="Serial"
            value={value}
            onChangeText={onChange}
            placeholder="e.g. 7f3c9a2e-4b81-…"
            autoCapitalize="none"
            autoFocus
            returnKeyType="go"
            onSubmitEditing={onSubmit}
          />
          <Button title="Check this unit" onPress={onSubmit} style={styles.modalAction} />
          <Button
            title="Cancel"
            variant="ghost"
            onPress={onCancel}
            style={styles.modalCancel}
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  topBar: { position: 'absolute', top: 0, left: 0, right: 0, zIndex: 2 },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  frame: { width: 260, height: 260 },
  corner: {
    position: 'absolute',
    width: 44,
    height: 44,
    borderColor: colors.accent,
  },
  cornerTl: { top: 0, left: 0, borderTopWidth: 4, borderLeftWidth: 4, borderTopLeftRadius: 18 },
  cornerTr: { top: 0, right: 0, borderTopWidth: 4, borderRightWidth: 4, borderTopRightRadius: 18 },
  cornerBl: {
    bottom: 0,
    left: 0,
    borderBottomWidth: 4,
    borderLeftWidth: 4,
    borderBottomLeftRadius: 18,
  },
  cornerBr: {
    bottom: 0,
    right: 0,
    borderBottomWidth: 4,
    borderRightWidth: 4,
    borderBottomRightRadius: 18,
  },
  hint: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '600',
    marginTop: spacing.xl,
    backgroundColor: 'rgba(14,51,70,0.65)',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    overflow: 'hidden',
  },
  controls: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  controlButton: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.16)',
  },
  controlButtonOn: { backgroundColor: colors.accent },
  controlIcon: { fontSize: 20 },
  controlLabel: { color: '#fff', fontSize: 11, fontWeight: '600', marginTop: 2 },
  controlLabelOn: { color: '#fff' },
  manualButton: {
    flex: 1,
    height: 64,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.16)',
  },
  manualText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  permission: { flex: 1, paddingHorizontal: spacing.xl, justifyContent: 'center' },
  permIcon: { fontSize: 40 },
  permTitle: { fontSize: 26, fontWeight: '800', color: colors.text, marginTop: spacing.md },
  permBody: { fontSize: 16, color: colors.muted, marginTop: spacing.sm, lineHeight: 23 },
  permAction: { marginTop: spacing.lg },
  permSecondary: { marginTop: spacing.sm },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(14,51,70,0.5)',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.lg,
  },
  modalTitle: { fontSize: 20, fontWeight: '800', color: colors.text },
  modalBody: { fontSize: 14, color: colors.muted, marginTop: spacing.xs, lineHeight: 20 },
  modalAction: { marginTop: spacing.lg },
  modalCancel: { marginTop: spacing.xs },
});
