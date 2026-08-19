import type { FormEvent } from 'react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError, friendlyMessage } from '../api/client';
import { lookupClaim } from '../api/public';
import type { ClaimResponse } from '../api/types';
import { Alert } from '../components/Alert';
import { Button } from '../components/Button';
import { TextField } from '../components/Field';
import { SkeletonCard } from '../components/SkeletonCard';
import { StatusPill } from '../components/StatusPill';
import { WarrantyCard } from '../components/WarrantyCard';
import { claimStatusMeta, formatDateTime, normalisePhone } from '../lib/format';
import { useAsync } from '../lib/useAsync';

/**
 * Reached two ways.
 *
 * `/claim/status` is someone who came looking. `/claims/:reference` is the link
 * the backend puts in the claim SMS (`{public_base_url}/claims/{reference}` —
 * see api/v1/public/claims.py), so that path has to exist and has to arrive with
 * the reference already filled in.
 *
 * The reference alone still shows nothing: the API wants the registered mobile
 * number too, which is what stops a forwarded link from being a claim viewer.
 */
export function ClaimStatusPage() {
  const { reference: fromLink } = useParams<{ reference?: string }>();
  const [reference, setReference] = useState(fromLink ?? '');
  const [phone, setPhone] = useState('');
  const [errors, setErrors] = useState<{ reference?: string; phone?: string }>({});
  const status = useAsync<ClaimResponse>();

  function clearError(key: 'reference' | 'phone') {
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const next: { reference?: string; phone?: string } = {};
    if (reference.trim().length < 4) next.reference = 'Enter the claim reference we gave you.';
    const normalised = normalisePhone(phone);
    if (!normalised) next.phone = 'Enter the 10-digit mobile number on the warranty.';
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    // Reference is upper-cased here rather than fussed over server-side: it is
    // read off a screenshot and retyped, and case is not information.
    void status.run(() => lookupClaim(reference.trim().toUpperCase(), normalised as string));
  }

  const notFound = status.status === 'error' && status.error instanceof ApiError && status.error.isNotFound;
  const claim = status.data;

  return (
    <>
      <Link className="back-link" to="/">
        ← Back to warranty check
      </Link>

      <div className="page-head">
        <h1>Track your claim</h1>
        <p>
          {fromLink
            ? 'We have your claim reference from the link. Enter the registered mobile number to see where it stands.'
            : 'Enter the reference from when you filed the claim, plus the registered mobile number.'}
        </p>
      </div>

      <form className="card stack" onSubmit={handleSubmit} noValidate>
        <TextField
          mono
          label="Claim reference"
          hint="Shown when you submitted the claim, and in the SMS we sent."
          value={reference}
          onChange={(event) => {
            setReference(event.target.value);
            clearError('reference');
          }}
          error={errors.reference}
          name="reference"
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
        />
        <TextField
          label="Registered mobile number"
          value={phone}
          onChange={(event) => {
            setPhone(event.target.value);
            clearError('phone');
          }}
          error={errors.phone}
          name="phone"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          placeholder="98765 43210"
        />
        <Button type="submit" loading={status.status === 'loading'} loadingLabel="Checking…">
          Check claim status
        </Button>
      </form>

      <div aria-live="polite" aria-busy={status.status === 'loading'}>
        {status.status === 'loading' ? (
          <div style={{ marginTop: '1.5rem' }}>
            <SkeletonCard />
          </div>
        ) : null}

        {notFound ? (
          <div style={{ marginTop: '1.5rem' }}>
            <Alert kind="warning" title="No claim found">
              We could not find a claim with that reference and mobile number together. Check both —
              the reference is case-insensitive, but the mobile number must be the one the warranty
              is registered to.
            </Alert>
          </div>
        ) : null}

        {status.status === 'error' && !notFound ? (
          <div style={{ marginTop: '1.5rem' }}>
            <Alert kind="error" title="We could not check that just now">
              {friendlyMessage(status.error)}
            </Alert>
          </div>
        ) : null}

        {claim ? (
          <>
            <p className="results-heading">Claim {claim.reference}</p>
            <div className="card stack--tight" style={{ display: 'flex', flexDirection: 'column' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.75rem',
                }}
              >
                <h2 className="card__title" style={{ margin: 0 }}>
                  Status
                </h2>
                <StatusPill {...claimStatusMeta(claim.status)} />
              </div>
              {/* The server writes one sentence per status. Preferred over our
                  own copy because it is the same wording the SMS uses, and a
                  customer comparing the two should not find them disagreeing. */}
              <p className="card__note">{claim.message || claimStatusMeta(claim.status).headline}</p>

              <dl className="facts" style={{ marginTop: '0.5rem' }}>
                <dt>Filed on</dt>
                <dd>{formatDateTime(claim.created_at)}</dd>
                {claim.issue_type ? (
                  <>
                    <dt>Reported as</dt>
                    <dd>{claim.issue_type}</dd>
                  </>
                ) : null}
                <dt>Problem reported</dt>
                <dd>{claim.description}</dd>
                {claim.resolved_at ? (
                  <>
                    <dt>Closed on</dt>
                    <dd>{formatDateTime(claim.resolved_at)}</dd>
                  </>
                ) : null}
              </dl>

              {claim.resolution_note ? (
                <Alert kind="info" title="Note from GoodBed">
                  {claim.resolution_note}
                </Alert>
              ) : null}
            </div>

            <p className="results-heading">The warranty this claim is against</p>
            <WarrantyCard warranty={claim.warranty} />
          </>
        ) : null}
      </div>
    </>
  );
}
