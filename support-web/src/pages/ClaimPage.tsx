import type { FormEvent } from 'react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { friendlyMessage } from '../api/client';
import { lookupWarranties, submitClaim } from '../api/public';
import type { ClaimResponse, LookupResponse, RedactedWarranty } from '../api/types';
import { Alert } from '../components/Alert';
import { Button } from '../components/Button';
import { SelectField, TextAreaField, TextField } from '../components/Field';
import { RegisterCta } from '../components/RegisterCta';
import { SkeletonCard } from '../components/SkeletonCard';
import { WarrantyCard } from '../components/WarrantyCard';
import { formatDate, normalisePhone, phoneMatchesMask, statusMeta } from '../lib/format';
import { useAsync } from '../lib/useAsync';

/** Values are slugs, not sentences: they land in `claims.issue_type` and get
 *  grouped in admin reporting, so they must survive a copy edit to the labels. */
const ISSUE_TYPES = [
  { value: 'sagging', label: 'Sagging or permanent body impression' },
  { value: 'foam_defect', label: 'Foam or filling has broken down' },
  { value: 'stitching', label: 'Stitching, seam or fabric damage' },
  { value: 'cover_zip', label: 'Cover or zip problem' },
  { value: 'comfort', label: 'Firmness or comfort is not as sold' },
  { value: 'other', label: 'Something else' },
];

/**
 * A claim only makes sense against a warranty that is actually running.
 *
 * Mirrors the backend's `_assert_claimable`: it rejects `voided`, the three
 * pending states, and anything past its end date (which reaches us already
 * folded into the status as `expired`). Checked here only so the page can
 * explain itself in place instead of taking the customer through a form to a
 * 409 — the server remains the one that decides.
 */
function canClaim(warranty: RedactedWarranty): boolean {
  return warranty.status === 'active' || warranty.status === 'claimed';
}

export function ClaimPage() {
  const [params] = useSearchParams();
  const [serial, setSerial] = useState(params.get('serial') ?? '');
  const [phone, setPhone] = useState('');
  const [findErrors, setFindErrors] = useState<{ serial?: string; phone?: string }>({});
  const find = useAsync<LookupResponse>();

  const [selected, setSelected] = useState<RedactedWarranty | null>(null);
  const [issueType, setIssueType] = useState('');
  const [description, setDescription] = useState('');
  const [formErrors, setFormErrors] = useState<{ issueType?: string; description?: string }>({});
  const claim = useAsync<ClaimResponse>();

  /** Errors clear as soon as the field is edited — a corrected form should not
   *  keep showing red for a problem the customer already fixed. */
  function clearFind(key: 'serial' | 'phone') {
    setFindErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  }

  function clearForm(key: 'issueType' | 'description') {
    setFormErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  }

  function handleFind(event: FormEvent) {
    event.preventDefault();
    const next: { serial?: string; phone?: string } = {};
    if (serial.trim().length < 4) next.serial = 'Enter the serial number on the mattress label.';
    const normalised = normalisePhone(phone);
    if (!normalised) next.phone = 'Enter the 10-digit mobile number the warranty is registered to.';
    setFindErrors(next);
    if (Object.keys(next).length > 0) return;

    setSelected(null);
    // Serial only. `POST /public/lookup` takes one identifier or the other and
    // 422s on both, so the pair cannot be checked here — the mobile number is
    // the possession check on `POST /public/claims`, and the server matches the
    // two when the claim is filed.
    void find.run(() => lookupWarranties({ kind: 'serial', value: serial.trim() }));
  }

  function handleSubmitClaim(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;

    const next: { issueType?: string; description?: string } = {};
    if (!issueType) next.issueType = 'Choose what is wrong with the mattress.';
    if (description.trim().length < 20) {
      next.description = 'Please describe the problem in a sentence or two (at least 20 characters).';
    }
    setFormErrors(next);
    if (Object.keys(next).length > 0) return;

    void claim.run(() =>
      submitClaim({
        serial: selected.serial,
        phone: normalisePhone(phone) as string,
        issueType,
        description: description.trim(),
      }),
    );
  }

  if (claim.status === 'success' && claim.data) {
    return <ClaimFiledPanel claim={claim.data} />;
  }

  const found = find.data?.results ?? [];
  // The record's number comes back masked as `98****3210`. That is enough to
  // tell the customer their number does not match this mattress before they
  // write out the whole problem and get a flat 404 for it.
  const phoneMismatch =
    selected != null && phoneMatchesMask(phone, selected.customer.phone) === false;

  return (
    <>
      <Link className="back-link" to="/">
        ← Back to warranty check
      </Link>

      <div className="page-head">
        <h1>Raise a warranty claim</h1>
        <p>
          First find your warranty, then tell us what is wrong. You will get a reference number to
          keep.
        </p>
      </div>

      <form className="card stack" onSubmit={handleFind} noValidate>
        <h2 className="card__title">Step 1 — Find your warranty</h2>
        <TextField
          mono
          label="Serial number"
          hint="The long code on the mattress label."
          value={serial}
          onChange={(event) => {
            setSerial(event.target.value);
            clearFind('serial');
          }}
          error={findErrors.serial}
          name="serial"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />
        <TextField
          label="Registered mobile number"
          hint="The number the mattress was bought with. It has to match the record — that is how we know the warranty is yours."
          value={phone}
          onChange={(event) => {
            setPhone(event.target.value);
            clearFind('phone');
          }}
          error={findErrors.phone}
          name="phone"
          type="tel"
          inputMode="numeric"
          autoComplete="tel"
          placeholder="98765 43210"
        />
        <Button type="submit" variant="secondary" loading={find.status === 'loading'} loadingLabel="Searching…">
          Find my warranty
        </Button>
      </form>

      <div aria-live="polite" aria-busy={find.status === 'loading'}>
        {find.status === 'loading' ? (
          <div style={{ marginTop: '1.5rem' }}>
            <SkeletonCard />
          </div>
        ) : null}

        {find.status === 'error' ? (
          <div style={{ marginTop: '1.5rem' }}>
            <Alert kind="error" title="We could not look that up">
              {friendlyMessage(find.error)}
            </Alert>
          </div>
        ) : null}

        {find.status === 'success' && found.length === 0 ? (
          <div className="stack" style={{ marginTop: '1.5rem' }}>
            <Alert kind="warning" title="No warranty found for that serial number">
              {find.data?.message ??
                'We have no warranty on that serial number. Check what you typed against the mattress label.'}
            </Alert>
            {find.data?.can_self_register ? <RegisterCta serial={serial.trim() || undefined} /> : null}
          </div>
        ) : null}

        {find.status === 'success' && found.length > 0 ? (
          <>
            <p className="results-heading">Step 2 — Confirm this is the right mattress</p>
            <ul className="results-list">
              {found.map((warranty) => (
                <li key={warranty.id}>
                  <WarrantyCard
                    warranty={warranty}
                    actions={
                      canClaim(warranty) ? (
                        selected?.id === warranty.id ? (
                          <span className="pill pill--success">
                            <span className="pill__dot" aria-hidden="true" />
                            Selected
                          </span>
                        ) : (
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => setSelected(warranty)}
                          >
                            Claim on this one
                          </Button>
                        )
                      ) : (
                        <ClaimBlockedNote warranty={warranty} />
                      )
                    }
                  />
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>

      {selected ? (
        <form className="card stack" onSubmit={handleSubmitClaim} noValidate style={{ marginTop: '1rem' }}>
          <h2 className="card__title">Step 3 — Tell us what is wrong</h2>

          {phoneMismatch ? (
            <Alert kind="warning" title="That mobile number does not look right">
              This mattress is registered to {selected.customer.phone}. A claim can only be raised
              from the number on the record — check the number in step 1, or contact GoodBed if it
              has changed.
            </Alert>
          ) : null}

          <SelectField
            label="What is the problem?"
            value={issueType}
            onChange={(event) => {
              setIssueType(event.target.value);
              clearForm('issueType');
            }}
            error={formErrors.issueType}
            name="issue_type"
          >
            <option value="">Choose one…</option>
            {ISSUE_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </SelectField>

          <TextAreaField
            label="Describe the problem"
            hint="When did it start, and what do you notice? A few honest sentences help more than a long one."
            value={description}
            onChange={(event) => {
              setDescription(event.target.value);
              clearForm('description');
            }}
            error={formErrors.description}
            name="description"
            rows={5}
            maxLength={2000}
          />

          {claim.status === 'error' ? (
            <Alert kind="error" title="We could not file that claim">
              {friendlyMessage(claim.error)}
            </Alert>
          ) : null}

          <Button type="submit" loading={claim.status === 'loading'} loadingLabel="Sending…">
            Submit claim
          </Button>

          <p className="text-muted text-sm">
            A claim is reviewed by GoodBed. Someone will contact you on{' '}
            {normalisePhone(phone) ?? 'your mobile number'} — it is not decided automatically.
          </p>
        </form>
      ) : null}
    </>
  );
}

function ClaimBlockedNote({ warranty }: { warranty: RedactedWarranty }) {
  const meta = statusMeta(warranty.status);
  const detail =
    warranty.status === 'expired'
      ? `This warranty ended on ${formatDate(warranty.warranty_end_date)}, so a claim cannot be raised against it.`
      : `${meta.headline} A claim cannot be raised against it right now.`;
  return (
    <Alert kind="warning" title={`Cannot claim — ${meta.label.toLowerCase()}`}>
      {detail}
    </Alert>
  );
}

function ClaimFiledPanel({ claim }: { claim: ClaimResponse }) {
  return (
    <>
      <div className="page-head">
        <h1>Claim received</h1>
        <p>Write this reference down or take a screenshot. You will need it to check progress.</p>
      </div>

      <div className="card stack">
        <div className="reference">
          <div className="reference__label">Your claim reference</div>
          <div className="reference__value">{claim.reference}</div>
        </div>

        {/* The server's own sentence. It differs when this reply re-surfaces an
            already-open claim rather than creating one, and only the server
            knows which of the two happened. */}
        <Alert kind="success" title="We have it">
          {claim.message}
        </Alert>

        <p className="card__note">
          Filed on {formatDate(claim.created_at.slice(0, 10))} against{' '}
          {claim.warranty.model_name ?? 'your GoodBed mattress'}.
        </p>

        <div>
          <h2 className="card__title">What happens next</h2>
          <ul className="card__note" style={{ marginTop: '0.5rem' }}>
            <li>GoodBed reviews the claim and the warranty record behind it.</li>
            <li>You will be contacted on the registered mobile number.</li>
            <li>Keep the mattress and your bill as they are until then.</li>
          </ul>
        </div>

        <Link className="btn btn--secondary" to="/claim/status">
          Track this claim
        </Link>
        <Link className="btn btn--quiet" to="/">
          Back to warranty check
        </Link>
      </div>
    </>
  );
}
