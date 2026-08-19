import type { FormEvent } from 'react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { friendlyMessage } from '../api/client';
import { confirmWarranty, disputeWarranty, viewWarranty } from '../api/public';
import type { CustomerActionResponse, WarrantyView } from '../api/types';
import { Alert } from '../components/Alert';
import { Button } from '../components/Button';
import { TextAreaField, TextField } from '../components/Field';
import { SkeletonCard } from '../components/SkeletonCard';
import { WarrantyCard } from '../components/WarrantyCard';
import { useAsync } from '../lib/useAsync';

/**
 * The page the SMS link lands on.
 *
 * Its real job is not "show a warranty" — the customer can already do that from
 * the home page. It is to get a yes or a no from the person who actually holds
 * the phone, because a dealer-entered sale is a claim and this reply is the only
 * thing that turns it into evidence.
 *
 * The possession check is the last 4 digits of the registered number. It is
 * weak on its own, which is fine: the link itself was delivered to that number,
 * so the two together mean "you have this phone". Asking for the whole number
 * would be worse, not better — it would tell a stranger who guessed a warranty
 * id nothing, but it would also stop the genuine owner who is not sure which of
 * their two numbers the shop wrote down.
 *
 * The backend answers a wrong code and an unknown warranty id with the same 403
 * `invalid_link`, so this page must not turn a failed check into "no such
 * warranty" — it says "that did not match" for both, which is all it knows.
 */

const DISPUTE_REASONS = [
  {
    value: 'not_my_purchase',
    title: 'I did not buy this mattress',
    note: 'The sale was recorded against my number by mistake, or by someone else.',
  },
  {
    value: 'wrong_details',
    title: 'I bought it, but these details are wrong',
    note: 'Wrong model, wrong date, or the wrong shop is shown.',
  },
  {
    value: 'returned',
    title: 'I returned or cancelled this purchase',
    note: 'The mattress went back to the shop.',
  },
];

export function ConfirmPage() {
  const { warrantyId } = useParams<{ warrantyId: string }>();
  const [last4, setLast4] = useState('');
  const [last4Error, setLast4Error] = useState<string | null>(null);
  const verify = useAsync<WarrantyView>();

  const [mode, setMode] = useState<'view' | 'dispute'>('view');
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [reasonError, setReasonError] = useState<string | null>(null);
  const action = useAsync<CustomerActionResponse>();

  if (!warrantyId) {
    return (
      <>
        <div className="page-head">
          <h1>That link is incomplete</h1>
        </div>
        <Alert kind="error" title="We cannot open this warranty">
          The link seems to have been cut short. Open the full link from your SMS, or look your
          warranty up with your mobile number.
        </Alert>
        <div className="link-row">
          <Link className="btn btn--primary" to="/">
            Check my warranty
          </Link>
        </div>
      </>
    );
  }

  function handleVerify(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{4}$/.test(last4)) {
      setLast4Error('Enter the last 4 digits of the mobile number, for example 3210.');
      return;
    }
    setLast4Error(null);
    void verify.run(() => viewWarranty(warrantyId as string, last4));
  }

  function handleConfirm() {
    void action.run(() => confirmWarranty(warrantyId as string, last4));
  }

  function handleDispute(event: FormEvent) {
    event.preventDefault();
    if (!reason) {
      setReasonError('Choose the one that fits best.');
      return;
    }
    setReasonError(null);
    // The chosen reason and the free text go into the one `note` field the API
    // has, because that field is what an admin reads in the approvals queue.
    const chosen = DISPUTE_REASONS.find((option) => option.value === reason);
    const text = note.trim() ? `${chosen?.title}: ${note.trim()}` : (chosen?.title ?? reason);
    void action.run(() => disputeWarranty(warrantyId as string, last4, text));
  }

  // ---- after an action: the server's own sentence, never one we invented ----
  if (action.status === 'success' && action.data) {
    const confirmed = mode === 'view';
    return (
      <>
        <div className="page-head">
          <h1>{confirmed ? 'Thank you' : 'Thank you for telling us'}</h1>
        </div>
        <div className="card stack">
          <Alert kind={confirmed ? 'success' : 'info'} title={confirmed ? 'Confirmed' : 'Reported'}>
            {action.data.message}
          </Alert>
          {/* The action returns the warranty as it now stands, so the card is
              re-rendered from the reply rather than patched from stale state.
              A dispute deliberately leaves the status alone — the record only
              changes once a human has looked at it. */}
          <WarrantyCard warranty={action.data.warranty} />
          <Link className="btn btn--secondary" to="/">
            Back to warranty check
          </Link>
        </div>
      </>
    );
  }

  // ---- gate: prove possession of the registered phone ----------------------
  if (verify.status !== 'success' || !verify.data) {
    return (
      <>
        <div className="page-head">
          <h1>Confirm your mattress</h1>
          <p>
            A GoodBed warranty has been registered to your mobile number. Before we show it, please
            confirm the number is yours.
          </p>
        </div>

        <form className="card stack" onSubmit={handleVerify} noValidate>
          <TextField
            big
            mono
            label="Last 4 digits of your mobile number"
            hint="The number that received this message."
            value={last4}
            onChange={(event) => {
              setLast4(event.target.value.replace(/\D/g, '').slice(0, 4));
              if (last4Error) setLast4Error(null);
            }}
            error={last4Error}
            name="last4"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            maxLength={4}
            placeholder="3210"
          />

          {verify.status === 'error' ? (
            <Alert kind="error" title="That did not match">
              {friendlyMessage(verify.error, 'Those digits do not match this warranty. Try again.')}
            </Alert>
          ) : null}

          <Button type="submit" loading={verify.status === 'loading'} loadingLabel="Checking…">
            Show my warranty
          </Button>
        </form>

        <div aria-live="polite">
          {verify.status === 'loading' ? (
            <div style={{ marginTop: '1.5rem' }}>
              <SkeletonCard />
            </div>
          ) : null}
        </div>
      </>
    );
  }

  const { warranty, awaiting_confirmation: awaiting, already_confirmed: alreadyConfirmed } =
    verify.data;

  // ---- dispute: a plain form, not an accusation ----------------------------
  if (mode === 'dispute') {
    return (
      <>
        <button
          type="button"
          className="back-link"
          onClick={() => {
            setMode('view');
            action.reset();
          }}
          style={{ background: 'none', border: 0, cursor: 'pointer', padding: 0 }}
        >
          ← Back to my warranty
        </button>

        <div className="page-head">
          <h1>Tell us what is wrong</h1>
          <p>
            Nothing is held against you for reporting this. It is exactly what we need to hear —
            we will check it with the shop and put the record right.
          </p>
        </div>

        <form className="card stack" onSubmit={handleDispute} noValidate>
          <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
            <legend className="field__label" style={{ padding: 0 }}>
              What is the problem?
            </legend>
            <div className="stack--tight" style={{ display: 'flex', flexDirection: 'column' }}>
              {DISPUTE_REASONS.map((option) => (
                <label
                  key={option.value}
                  className={`choice${reason === option.value ? ' choice--selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="dispute_reason"
                    value={option.value}
                    checked={reason === option.value}
                    onChange={() => {
                      setReason(option.value);
                      setReasonError(null);
                    }}
                  />
                  <span>
                    <span className="choice__title">{option.title}</span>
                    <span className="choice__note">{option.note}</span>
                  </span>
                </label>
              ))}
            </div>
            {reasonError ? (
              <p className="field__error">
                <span aria-hidden="true">!</span>
                <span>{reasonError}</span>
              </p>
            ) : null}
          </fieldset>

          <TextAreaField
            label="Anything else we should know? (optional)"
            hint="For example, the shop name you actually bought from."
            value={note}
            onChange={(event) => setNote(event.target.value)}
            name="note"
            rows={4}
            maxLength={1000}
          />

          {action.status === 'error' ? (
            <Alert kind="error" title="We could not send that">
              {friendlyMessage(action.error)}
            </Alert>
          ) : null}

          <Button type="submit" loading={action.status === 'loading'} loadingLabel="Sending…">
            Send this report
          </Button>
        </form>
      </>
    );
  }

  // ---- the warranty, with the yes/no it exists to ask ----------------------
  return (
    <>
      <div className="page-head">
        <h1>Is this your mattress?</h1>
        <p>
          {/* `awaiting_confirmation` is the server saying this reply is the thing
              standing between the sale and an active warranty. When it is false
              the warranty is already running and confirming is an
              acknowledgement, so the page does not claim otherwise. */}
          {awaiting
            ? 'This warranty is waiting on your confirmation before it starts. Confirming it activates your cover.'
            : 'This warranty was registered to your mobile number. Confirming it records that the sale really is yours.'}
        </p>
      </div>

      <WarrantyCard warranty={warranty} />

      {alreadyConfirmed ? (
        <div style={{ marginTop: '1rem' }}>
          <Alert kind="success" title="Already confirmed">
            You have confirmed this mattress before. Nothing more is needed — but if something
            below is wrong, you can still tell us.
          </Alert>
        </div>
      ) : null}

      {action.status === 'error' ? (
        <div style={{ marginTop: '1rem' }}>
          <Alert kind="error" title="We could not record that">
            {friendlyMessage(action.error)}
          </Alert>
        </div>
      ) : null}

      <div className="card stack" style={{ marginTop: '1rem' }}>
        {!alreadyConfirmed ? (
          <Button
            type="button"
            onClick={handleConfirm}
            loading={action.status === 'loading'}
            loadingLabel="Saving…"
          >
            Yes, I bought this
          </Button>
        ) : null}
        <Button
          type="button"
          variant="quiet"
          disabled={action.status === 'loading'}
          onClick={() => setMode('dispute')}
        >
          I did not buy this
        </Button>
        <p className="text-muted text-sm">
          Not sure? Confirming only records that the mattress is yours. It does not start any
          process and costs you nothing.
        </p>
      </div>
    </>
  );
}
