import type { FormEvent } from 'react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { friendlyMessage } from '../api/client';
import { submitSelfRegistration } from '../api/public';
import type { SelfRegistrationResponse } from '../api/types';
import { Alert } from '../components/Alert';
import { Button } from '../components/Button';
import { TextField } from '../components/Field';
import { ProofUpload } from '../components/ProofUpload';
import { WarrantyCard } from '../components/WarrantyCard';
import { normalisePhone } from '../lib/format';
import { useAsync } from '../lib/useAsync';

interface Errors {
  serial?: string;
  name?: string;
  phone?: string;
  purchaseDate?: string;
  proof?: string;
}

/** Today in the browser's timezone, as YYYY-MM-DD. Used only to stop a future
 *  purchase date being typed; the authoritative clock is the server's. */
function todayIso(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function SelfRegisterPage() {
  const [params] = useSearchParams();
  const [serial, setSerial] = useState(params.get('serial') ?? '');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');
  const [invoiceRef, setInvoiceRef] = useState('');
  const [dealerHint, setDealerHint] = useState('');
  const [proof, setProof] = useState<File | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const submission = useAsync<SelfRegistrationResponse>();

  /** Clear a field's error the moment the customer starts fixing it. Leaving it
   *  on screen turns a corrected form into a wall of red and hides which field
   *  is still actually wrong. */
  function clearError(key: keyof Errors) {
    setErrors((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const next: Errors = {};

    if (serial.trim().length < 4) {
      next.serial = 'Enter the serial number printed on the mattress label.';
    }
    if (name.trim().length < 2) next.name = 'Enter your full name.';

    const normalisedPhone = normalisePhone(phone);
    if (!normalisedPhone) next.phone = 'Enter a valid 10-digit Indian mobile number.';

    if (!purchaseDate) next.purchaseDate = 'Enter the date on your bill.';
    else if (purchaseDate > todayIso()) next.purchaseDate = 'The purchase date cannot be in the future.';

    if (!proof) next.proof = 'Attach a photo of your bill so GoodBed can verify the purchase.';
    else if (errors.proof) next.proof = errors.proof;

    setErrors(next);
    if (Object.keys(next).length > 0) return;

    void submission.run(() =>
      submitSelfRegistration({
        serial: serial.trim(),
        customerName: name.trim(),
        customerPhone: normalisedPhone as string,
        purchaseDate,
        proof: proof as File,
        invoiceRef,
        dealerHint,
      }),
    );
  }

  if (submission.status === 'success' && submission.data) {
    return <SubmittedPanel result={submission.data} />;
  }

  return (
    <>
      <Link className="back-link" to="/">
        ← Back to warranty check
      </Link>

      <div className="page-head">
        <h1>Register your warranty</h1>
        <p>
          If the shop did not register your mattress at the time of sale, send the details here and
          GoodBed will check them against the bill.
        </p>
      </div>

      {/* Honesty first, and above the form rather than buried under the button:
          this is a queue with a human at the end of it, and a customer who
          expects an instant warranty card will feel cheated an hour later. */}
      <div style={{ marginBottom: '1.25rem' }}>
        <Alert kind="info" title="This goes to GoodBed for review">
          Your request is not active straight away. Someone at GoodBed checks the bill against the
          mattress record, and you will be contacted on the mobile number you enter below. Keep your
          original bill until then.
        </Alert>
      </div>

      <form className="card stack" onSubmit={handleSubmit} noValidate>
        <TextField
          mono
          label="Serial number"
          hint="The long code on the label sewn to the mattress, or under the QR sticker."
          value={serial}
          onChange={(event) => {
            setSerial(event.target.value);
            clearError('serial');
          }}
          error={errors.serial}
          name="serial"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          inputMode="text"
        />

        <TextField
          label="Your full name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            clearError('name');
          }}
          error={errors.name}
          name="name"
          autoComplete="name"
        />

        <TextField
          label="Your mobile number"
          hint="GoodBed will contact you on this number, so use the one you actually answer."
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

        <TextField
          label="Date of purchase"
          hint="The date printed on your bill."
          value={purchaseDate}
          onChange={(event) => {
            setPurchaseDate(event.target.value);
            clearError('purchaseDate');
          }}
          error={errors.purchaseDate}
          name="purchase_date"
          type="date"
          max={todayIso()}
        />

        {/* Both optional on the wire and both worth asking for: when the serial
            was never allocated to a dealer, the shop name is the only lead the
            compliance team has for finding out who sold it. */}
        <TextField
          label="Which shop did you buy it from? (optional)"
          hint="The shop name and area, as best you remember."
          value={dealerHint}
          onChange={(event) => setDealerHint(event.target.value)}
          name="dealer_hint"
          maxLength={200}
        />

        <TextField
          label="Bill or invoice number (optional)"
          hint="Printed on your bill, if you can find it."
          value={invoiceRef}
          onChange={(event) => setInvoiceRef(event.target.value)}
          name="invoice_ref"
          maxLength={120}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
        />

        <ProofUpload
          file={proof}
          error={errors.proof}
          onChange={(file, error) => {
            setProof(file);
            setErrors((prev) => ({ ...prev, proof: error ?? undefined }));
          }}
        />

        {submission.status === 'error' ? (
          <Alert kind="error" title="We could not send that">
            {friendlyMessage(submission.error)}
          </Alert>
        ) : null}

        <Button
          type="submit"
          loading={submission.status === 'loading'}
          loadingLabel="Sending…"
        >
          Send for review
        </Button>

        <p className="text-muted text-sm">
          By sending this you confirm the details are true and that you bought this mattress.
        </p>
      </form>
    </>
  );
}

/**
 * Two outcomes share this screen, and the server tells us which one happened.
 *
 * `already_registered` is not a failure and is not rare: the commonest reason a
 * customer reaches this form is that they could not find their warranty, and a
 * good share of those were registered by the dealer under a different serial
 * reading. Nothing new was created, the existing record is returned, and saying
 * "sent for review" there would be a straight lie.
 */
function SubmittedPanel({ result }: { result: SelfRegistrationResponse }) {
  const existing = result.status === 'already_registered';

  return (
    <>
      <div className="page-head">
        <h1>{existing ? 'This one is already registered' : 'Sent to GoodBed'}</h1>
        <p>
          {existing
            ? 'We found a warranty on this mattress already, so there was nothing to send.'
            : 'We have your registration request. Nothing more is needed from you right now.'}
        </p>
      </div>

      <div className="card stack">
        <Alert kind={existing ? 'info' : 'success'} title={existing ? 'Already on record' : 'Received'}>
          {result.message}
        </Alert>

        <WarrantyCard warranty={result.warranty} />

        {!existing ? (
          <div>
            <h2 className="card__title">What happens next</h2>
            <ul className="card__note" style={{ marginTop: '0.5rem' }}>
              <li>Someone at GoodBed checks your bill against the mattress record.</li>
              <li>You will be contacted on the mobile number you gave us.</li>
              <li>
                If it is approved, your warranty is dated from the purchase date on your bill — not
                from today.
              </li>
            </ul>
          </div>
        ) : null}

        <p className="text-muted text-sm">
          {existing
            ? 'If the details above are not yours, contact GoodBed support — do not register it again.'
            : 'Keep your original bill safe until GoodBed confirms. You can check the status any time by searching your mobile number on the home page.'}
        </p>

        <Link className="btn btn--secondary" to="/">
          Back to warranty check
        </Link>
      </div>
    </>
  );
}
