import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'quiet';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
  loadingLabel?: string;
  children: ReactNode;
}

export function Button({
  variant = 'primary',
  loading = false,
  loadingLabel = 'Working…',
  disabled,
  children,
  className,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={`btn btn--${variant}${className ? ` ${className}` : ''}`}
      disabled={disabled || loading}
      // aria-busy rather than swapping the accessible name mid-press: a screen
      // reader user should not be told the button "became" something else.
      aria-busy={loading || undefined}
    >
      {loading ? <span className="spinner" aria-hidden="true" /> : null}
      <span>{loading ? loadingLabel : children}</span>
    </button>
  );
}
