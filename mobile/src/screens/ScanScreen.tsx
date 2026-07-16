import { CameraView, useCameraPermissions } from 'expo-camera';
import React, { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { extractApiError } from '../api/client';
import { Button } from '../components/Button';
import { ScanResultSheet, type ScanOutcome } from '../components/ScanResultSheet';
import { ScreenBackground } from '../components/ScreenBackground';
import { useClaim } from '../hooks/useClaim';
import { useI18n } from '../i18n/I18nProvider';
import { colors, spacing } from '../theme';

export function ScanScreen() {
  const { t } = useI18n();
  const [permission, requestPermission] = useCameraPermissions();
  const claim = useClaim();
  const [outcome, setOutcome] = useState<ScanOutcome>(null);
  // Guard so a single QR in frame fires the claim only once.
  const lockedRef = useRef(false);

  const handleScan = ({ data }: { data: string }) => {
    if (lockedRef.current) return;
    lockedRef.current = true;

    claim.mutate(data, {
      onSuccess: (result) => setOutcome({ kind: 'success', result }),
      onError: (e) => {
        const api = extractApiError(e);
        if (api?.code === 'already_claimed') {
          setOutcome({
            kind: 'duplicate',
            claimedAt: (api.details?.claimed_at as string | undefined) ?? null,
          });
        } else if (api?.code === 'invalid_code') {
          setOutcome({ kind: 'error', title: t('result.unknownTitle'), message: t('result.unknownBody') });
        } else if (api?.code === 'code_void') {
          setOutcome({ kind: 'error', title: t('result.voidTitle'), message: t('result.voidBody') });
        } else {
          setOutcome({
            kind: 'error',
            title: t('result.errTitle'),
            message: api?.message ?? t('result.errBody'),
          });
        }
      },
    });
  };

  const reset = () => {
    setOutcome(null);
    lockedRef.current = false;
  };

  if (!permission) {
    return (
      <ScreenBackground>
        <View style={styles.center} />
      </ScreenBackground>
    );
  }

  if (!permission.granted) {
    return (
      <ScreenBackground>
        <View style={styles.center}>
          <Text style={styles.permTitle}>{t('scan.permTitle')}</Text>
          <Text style={styles.permBody}>{t('scan.permBody')}</Text>
          <Button title={t('scan.grant')} onPress={requestPermission} style={{ marginTop: spacing.lg }} />
        </View>
      </ScreenBackground>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={outcome ? undefined : handleScan}
      />
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.frame} />
        <Text style={styles.hint}>
          {claim.isPending ? t('scan.claiming') : t('scan.hint')}
        </Text>
      </View>
      <ScanResultSheet outcome={outcome} onDismiss={reset} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  permTitle: { fontSize: 20, fontWeight: '700', color: colors.text },
  permBody: { fontSize: 15, color: colors.muted, textAlign: 'center', marginTop: spacing.sm },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  frame: {
    width: 240,
    height: 240,
    borderWidth: 3,
    borderColor: '#fff',
    borderRadius: 24,
    backgroundColor: 'transparent',
  },
  hint: {
    color: '#fff',
    fontSize: 16,
    marginTop: spacing.lg,
    backgroundColor: 'rgba(0,0,0,0.5)',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 8,
    overflow: 'hidden',
  },
});
