import type { ReactNode } from 'react';

import type { RedactedWarranty } from '../api/types';
import { formatDate, formatDateTime, formatMonths, formatPhone, statusMeta } from '../lib/format';
import { StatusPill } from './StatusPill';

interface WarrantyCardProps {
  warranty: RedactedWarranty;
  /** Buttons rendered under the card — "Raise a claim", "Confirm", and so on. */
  actions?: ReactNode;
}

export function WarrantyCard({ warranty, actions }: WarrantyCardProps) {
  const meta = statusMeta(warranty.status);

  return (
    <article className="warranty">
      <header className="warranty__head">
        <div>
          <h2 className="warranty__model">{warranty.model_name ?? 'GoodBed mattress'}</h2>
          <p className="warranty__headline">{meta.headline}</p>
        </div>
        <StatusPill label={meta.label} tone={meta.tone} />
      </header>

      <div className="warranty__body">
        <dl className="facts">
          <dt>Warranty period</dt>
          <dd>
            {formatDate(warranty.warranty_start_date)} – {formatDate(warranty.warranty_end_date)}
          </dd>

          <dt>Cover length</dt>
          <dd>{formatMonths(warranty.warranty_months)}</dd>

          <dt>Registered on</dt>
          <dd>{formatDateTime(warranty.registered_at)}</dd>

          <dt>Registered to</dt>
          <dd>
            {/* Always masked, whichever way the warranty was found. Printed
                exactly as the server sent it — the client has no business
                reconstructing a customer's name or number. */}
            {warranty.customer.name}
            <br />
            <span className="text-muted">{formatPhone(warranty.customer.phone)}</span>
          </dd>

          {/* Newer warranties have no serial — they are identified by the
              invoice number, which is what the customer has on their bill. */}
          <dt>{warranty.serial ? 'Serial' : 'Invoice'}</dt>
          <dd className="mono">{warranty.serial ?? warranty.reference}</dd>
        </dl>
      </div>

      <div className="warranty__foot">
        <div className="warranty__seller">
          <div className="warranty__seller-label">Sold by</div>
          {warranty.dealer ? (
            <>
              <div className="warranty__seller-name">{warranty.dealer.name}</div>
              {warranty.dealer.city ? (
                <div className="warranty__seller-city">{warranty.dealer.city}</div>
              ) : null}
            </>
          ) : (
            <div className="warranty__seller-city">
              {warranty.source === 'customer_self'
                ? 'You registered this warranty yourself. The shop is not on record.'
                : 'The selling shop is not on record.'}
            </div>
          )}
        </div>

        {/* Unconditional, because the masking is: the public API never returns a
            customer's full name or number, so an explanation that appears only
            sometimes would be a lie about the other times. */}
        <p className="text-muted text-sm" style={{ marginTop: '0.75rem' }}>
          The name and mobile number are partly hidden to protect the buyer's privacy. GoodBed
          support can see them in full.
        </p>

        {actions ? <div className="link-row">{actions}</div> : null}
      </div>
    </article>
  );
}
