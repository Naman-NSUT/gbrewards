import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { SUPPORT_EMAIL, SUPPORT_PHONE } from '../config';

function BrandMark() {
  return (
    <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#184860" />
      <path
        d="M6 19.5v-6.2A1.6 1.6 0 0 1 7.6 11.7h16.8a1.6 1.6 0 0 1 1.6 1.6v6.2"
        fill="none"
        stroke="#0090D8"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <rect x="6" y="19" width="20" height="5" rx="1.8" fill="#EEF4F8" />
    </svg>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="masthead">
        <div className="masthead__inner">
          <Link className="brand" to="/">
            <BrandMark />
            <span className="brand__name">
              GoodBed
              <span className="brand__sub">Warranty support</span>
            </span>
          </Link>
        </div>
      </header>

      <main className="main" id="main">
        {children}
      </main>

      <footer className="colophon">
        <p>The official warranty service for GoodBed mattresses.</p>
        {SUPPORT_PHONE || SUPPORT_EMAIL ? (
          <p>
            Need a person?{' '}
            {SUPPORT_PHONE ? <a href={`tel:${SUPPORT_PHONE}`}>{SUPPORT_PHONE}</a> : null}
            {SUPPORT_PHONE && SUPPORT_EMAIL ? ' · ' : null}
            {SUPPORT_EMAIL ? <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a> : null}
          </p>
        ) : null}
        <p>
          <Link to="/">Check a warranty</Link> · <Link to="/register">Register a warranty</Link> ·{' '}
          <Link to="/claim">Raise a claim</Link> · <Link to="/claim/status">Track a claim</Link>
        </p>
      </footer>
    </div>
  );
}
