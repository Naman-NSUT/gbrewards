import { DownloadOutlined, FileImageOutlined, WarningOutlined } from '@ant-design/icons';
import { Button, Spin } from 'antd';
import { useEffect, useState } from 'react';

import { apiErrorCode, apiErrorMessage } from '../api/client';
import { fetchProof } from '../api/proofs';
import { brand } from '../theme';

/**
 * The invoice behind a self-registration, shown next to the decision.
 *
 * A self-registration is an anonymous claim that a sale happened, and this
 * photo is the only evidence for it. The queue used to print the object-store
 * key as text, so the approver committed the company to a five-year warranty
 * without ever seeing what they were approving.
 *
 * HEIC is fetched and offered as a download rather than rendered: iPhones
 * produce it by default and almost no browser will paint it, so an <img> would
 * show a broken icon and read as "no evidence" for the single most common
 * camera among the customers using this.
 *
 * Give this a `key` of the same warranty id you pass in. It starts in its
 * loading state and only leaves it from an async callback, so a caller that
 * swaps warrantyId without remounting would show the previous invoice until the
 * new one arrives — and on this screen that is the wrong customer's evidence
 * beside a live approve button.
 */
export function ProofPreview({ warrantyId, height = 220 }: { warrantyId: string; height?: number }) {
  const [state, setState] = useState<
    | { kind: 'loading' }
    | { kind: 'ready'; url: string; contentType: string }
    | { kind: 'empty'; message: string }
    | { kind: 'error'; message: string }
  >({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    fetchProof(warrantyId)
      .then((proof) => {
        if (cancelled) {
          // Unmounted mid-flight — nothing will revoke this but us.
          URL.revokeObjectURL(proof.url);
          return;
        }
        objectUrl = proof.url;
        setState({ kind: 'ready', url: proof.url, contentType: proof.contentType });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        // "never attached" is a normal state for a backdate request; anything
        // else is a problem the approver has to weigh, so it is not styled as
        // a quiet empty slot.
        const kind = apiErrorCode(error) === 'no_proof' ? 'empty' : 'error';
        setState({ kind, message: apiErrorMessage(error, 'Could not load the invoice') });
      });

    return () => {
      cancelled = true;
      // Revoke on unmount: this queue is worked all day, and every invoice
      // looked at would otherwise be held in memory for the life of the tab.
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [warrantyId]);

  const frame = (children: React.ReactNode, tone: string) => (
    <div
      style={{
        marginTop: 6,
        minHeight: 88,
        height,
        display: 'grid',
        placeItems: 'center',
        border: `1px dashed ${brand.border}`,
        borderRadius: 8,
        color: tone,
        fontSize: 12,
        gap: 6,
        padding: 10,
        textAlign: 'center',
        overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );

  if (state.kind === 'loading') return frame(<Spin size="small" />, brand.textFaint);

  if (state.kind === 'empty')
    return frame(
      <>
        <FileImageOutlined />
        <span>{state.message}</span>
      </>,
      brand.textFaint,
    );

  if (state.kind === 'error')
    return frame(
      <>
        <WarningOutlined style={{ color: brand.warning }} />
        <span style={{ maxWidth: 260 }}>{state.message}</span>
      </>,
      brand.textDim,
    );

  const isImage = state.contentType.startsWith('image/') && !state.contentType.includes('heic');

  if (isImage)
    return (
      <a href={state.url} target="_blank" rel="noreferrer" title="Open full size">
        <img
          src={state.url}
          alt="Invoice supplied by the customer"
          style={{
            marginTop: 6,
            width: '100%',
            height,
            objectFit: 'contain',
            background: brand.elevated,
            border: `1px solid ${brand.border}`,
            borderRadius: 8,
            cursor: 'zoom-in',
          }}
        />
      </a>
    );

  if (state.contentType === 'application/pdf')
    return (
      <iframe
        src={state.url}
        title="Invoice supplied by the customer"
        style={{
          marginTop: 6,
          width: '100%',
          height,
          border: `1px solid ${brand.border}`,
          borderRadius: 8,
          background: brand.elevated,
        }}
      />
    );

  // HEIC, or anything else the whitelist starts accepting later.
  return frame(
    <>
      <FileImageOutlined />
      <span>This invoice cannot be shown in a browser.</span>
      <Button
        size="small"
        icon={<DownloadOutlined />}
        href={state.url}
        download={`invoice-${warrantyId}`}
      >
        Download
      </Button>
    </>,
    brand.textDim,
  );
}
