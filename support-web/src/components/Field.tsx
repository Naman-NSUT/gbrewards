import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';
import { useId } from 'react';

/**
 * Every control on this site is built from these three, so the label/hint/error
 * wiring is written once and cannot be forgotten on the one form that matters.
 * `id` is generated rather than passed: a hand-written id is the usual way a
 * label quietly stops pointing at its input.
 */

interface Shared {
  label: string;
  hint?: ReactNode;
  error?: string | null;
}

function useFieldIds(error?: string | null, hint?: ReactNode) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;
  return { id, hintId, errorId, describedBy };
}

function Wrapper({
  label,
  hint,
  error,
  id,
  hintId,
  errorId,
  className,
  children,
}: Shared & {
  id: string;
  hintId?: string;
  errorId?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`field${error ? ' field--invalid' : ''}${className ? ` ${className}` : ''}`}>
      {/* The hint is a SIBLING of the label, not a child of it. Nested, it would
          become part of the input's accessible name, so a screen reader would
          read the entire explanation back every time focus lands on the field.
          As a sibling it is referenced by aria-describedby instead. */}
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {hint ? (
        <p className="field__hint" id={hintId}>
          {hint}
        </p>
      ) : null}
      {children}
      {error ? (
        <p className="field__error" id={errorId}>
          <span aria-hidden="true">!</span>
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> &
  Shared & { big?: boolean; mono?: boolean };

export function TextField({ label, hint, error, big, mono, ...rest }: TextFieldProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(error, hint);
  return (
    <Wrapper
      label={label}
      hint={hint}
      error={error}
      id={id}
      hintId={hintId}
      errorId={errorId}
      className={big ? 'field--big' : undefined}
    >
      <input
        {...rest}
        id={id}
        className={`field__control${mono ? ' field__control--mono' : ''}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
    </Wrapper>
  );
}

type TextAreaFieldProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> & Shared;

export function TextAreaField({ label, hint, error, ...rest }: TextAreaFieldProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(error, hint);
  return (
    <Wrapper label={label} hint={hint} error={error} id={id} hintId={hintId} errorId={errorId}>
      <textarea
        {...rest}
        id={id}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
    </Wrapper>
  );
}

type SelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> &
  Shared & { children: ReactNode };

export function SelectField({ label, hint, error, children, ...rest }: SelectFieldProps) {
  const { id, hintId, errorId, describedBy } = useFieldIds(error, hint);
  return (
    <Wrapper label={label} hint={hint} error={error} id={id} hintId={hintId} errorId={errorId}>
      <select
        {...rest}
        id={id}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      >
        {children}
      </select>
    </Wrapper>
  );
}
