import { Html5Qrcode } from 'html5-qrcode';
import { useEffect, useRef } from 'react';

const ELEMENT_ID = 'sr-webcam-scanner';

export function WebcamScanner({ onDecode }: { onDecode: (text: string) => void }) {
  const scannerRef = useRef<Html5Qrcode | null>(null);
  const onDecodeRef = useRef(onDecode);

  useEffect(() => {
    onDecodeRef.current = onDecode;
  });

  useEffect(() => {
    const scanner = new Html5Qrcode(ELEMENT_ID);
    scannerRef.current = scanner;
    let stopped = false;

    scanner
      .start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: 250 },
        (decodedText) => {
          if (!stopped) {
            stopped = true;
            onDecodeRef.current(decodedText);
            void scanner.stop().catch(() => undefined);
          }
        },
        () => undefined,
      )
      .catch(() => undefined);

    return () => {
      if (!stopped) {
        void scanner.stop().catch(() => undefined);
      }
    };
  }, []);

  return <div id={ELEMENT_ID} style={{ width: '100%' }} />;
}
