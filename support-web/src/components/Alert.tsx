import type { ReactNode } from 'react';

type Kind = 'error' | 'warning' | 'success' | 'info';

interface AlertProps {
  kind: Kind;
  title?: string;
  children: ReactNode;
}

const ICONS: Record<Kind, ReactNode> = {
  error: <path d="M12 8v5m0 3.5h.01M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20.2h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />,
  warning: <path d="M12 8v5m0 3.5h.01M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20.2h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />,
  success: <path d="M20 6 9 17l-5-5" />,
  info: <path d="M12 16v-5m0-3.5h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />,
};

export function Alert({ kind, title, children }: AlertProps) {
  return (
    <div
      className={`alert alert--${kind}`}
      // Errors interrupt; confirmations do not. `assertive` on a success message
      // would talk over whatever the customer is already reading.
      role={kind === 'error' ? 'alert' : 'status'}
    >
      <svg
        className="alert__icon"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {ICONS[kind]}
      </svg>
      <div className="alert__body">
        {title ? <strong>{title}</strong> : null}
        {children}
      </div>
    </div>
  );
}
