import type { FormEvent } from 'react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { lookupWarranties } from '../api/public';
import type { LookupResponse } from '../api/types';
import { friendlyMessage } from '../api/client';
import { Alert } from '../components/Alert';
import { Button } from '../components/Button';
import { TextField } from '../components/Field';
import { RegisterCta } from '../components/RegisterCta';
import { SkeletonCard } from '../components/SkeletonCard';
import { WarrantyCard } from '../components/WarrantyCard';
import { classifyQuery, formatPhone } from '../lib/format';
import { useAsync } from '../lib/useAsync';

export function LookupPage() {
  const [query, setQuery] = useState('');
  const [fieldError, setFieldError] = useState<string | null>(null);
  /** The query the visible results belong to — used to prefill self-registration
   *  with the serial the customer already typed. */
  const [searched, setSearched] = useState<{ kind: 'phone' | 'serial'; value: string } | null>(null);
  const lookup = useAsync<LookupResponse>();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const raw = query.trim();

    if (!raw) {
      setFieldError('Enter your mobile number or the serial number on the mattress.');
      return;
    }
    // A short run of digits is a half-typed phone number far more often than it
    // is a serial, and telling someone "no warranty found" for a typo is cruel.
    if (/^\d+$/.test(raw) && raw.length < 10) {
      setFieldError('That mobile number looks incomplete. Enter all 10 digits.');
      return;
    }

    // One box, two searches: `POST /public/lookup` takes a phone or a serial and
    // rejects both together, so the decision has to be made here before asking.
    const parsed = classifyQuery(raw);
    setFieldError(null);
    setSearched(parsed);
    void lookup.run(() => lookupWarranties(parsed));
  }

  const results = lookup.data?.results ?? [];
  // `can_self_register` is the server's own signal, not something inferred from
  // an empty list — it stays true for a serial we have never heard of precisely
  // so it cannot be read as "this serial exists".
  const foundNothing = lookup.status === 'success' && results.length === 0;
  const canSelfRegister = lookup.data?.can_self_register ?? false;

  return (
    <>
      <div className="page-head">
        <h1>Check your GoodBed warranty</h1>
        <p>
          See whether the warranty on your mattress is registered and valid — enter the mobile
          number it was bought with, or the serial number on the mattress label.
        </p>
      </div>

      <form className="card" onSubmit={handleSubmit} noValidate>
        <TextField
          big
          label="Mobile number or serial number"
          hint="For example 98765 43210, or the long code on the label sewn to your mattress."
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            if (fieldError) setFieldError(null);
          }}
          error={fieldError}
          name="query"
          autoComplete="tel"
          enterKeyHint="search"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          placeholder="98765 43210"
        />
        <div style={{ marginTop: '1rem' }}>
          <Button type="submit" loading={lookup.status === 'loading'} loadingLabel="Checking…">
            Check warranty
          </Button>
        </div>
      </form>

      {/* Results live below the form, so nothing above them ever moves. */}
      <div aria-live="polite" aria-busy={lookup.status === 'loading'}>
        {lookup.status === 'loading' ? (
          <>
            <p className="results-heading">Checking…</p>
            <SkeletonCard />
          </>
        ) : null}

        {lookup.status === 'error' ? (
          <div style={{ marginTop: '1.5rem' }}>
            <Alert kind="error" title="We could not check that just now">
              {friendlyMessage(lookup.error)}
            </Alert>
          </div>
        ) : null}

        {lookup.status === 'success' && results.length > 0 ? (
          <>
            <p className="results-heading">
              {results.length === 1 ? '1 warranty found' : `${results.length} warranties found`}
            </p>
            <ul className="results-list">
              {results.map((warranty) => (
                <li key={warranty.id}>
                  <WarrantyCard
                    warranty={warranty}
                    actions={
                      warranty.status === 'active' ? (
                        <Link
                          className="btn btn--secondary"
                          to={`/claim?serial=${encodeURIComponent(warranty.reference)}`}
                        >
                          Raise a claim
                        </Link>
                      ) : undefined
                    }
                  />
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {foundNothing ? (
          <div className="stack" style={{ marginTop: '1.5rem' }}>
            <Alert kind="warning" title="No warranty found for that">
              We have no registered warranty for{' '}
              <strong style={{ display: 'inline' }}>
                {searched?.kind === 'phone' ? formatPhone(searched.value) : searched?.value}
              </strong>
              .{' '}
              {/* The server writes this sentence, and it is written to be shown —
                  it explains the next step without confirming or denying that
                  the serial itself exists. */}
              {lookup.data?.message ?? 'Double-check what you typed and try again.'}
            </Alert>
            {canSelfRegister ? (
              <RegisterCta serial={searched?.kind === 'serial' ? searched.value : undefined} />
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="divider" />

      <div className="card">
        <h2 className="card__title">Already registered?</h2>
        <p className="card__note">
          If something is wrong with your mattress, raise a warranty claim and GoodBed will get in
          touch.
        </p>
        <div className="link-row">
          <Link className="btn btn--secondary" to="/claim">
            Raise a claim
          </Link>
          <Link className="btn btn--secondary" to="/claim/status">
            Track a claim
          </Link>
        </div>
      </div>
    </>
  );
}
