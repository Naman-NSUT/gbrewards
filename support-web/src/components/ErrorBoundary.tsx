import type { ReactNode } from 'react';
import { Component } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/**
 * A render crash on a public page must not become a white screen.
 *
 * There is no error reporting wired up here on purpose: this site is
 * unauthenticated and anonymous, and shipping a telemetry SDK to it to catch a
 * rare render bug would mean loading a third-party script on every customer's
 * phone. The server logs the API side; this only has to fail politely.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="card">
        <h1 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Something went wrong</h1>
        <p className="card__note">
          This page could not be displayed. Reloading usually fixes it.
        </p>
        <div style={{ marginTop: '1rem' }}>
          <button type="button" className="btn btn--primary" onClick={() => window.location.reload()}>
            Reload the page
          </button>
        </div>
      </div>
    );
  }
}
