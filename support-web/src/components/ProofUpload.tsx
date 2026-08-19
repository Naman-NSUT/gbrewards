import type { ChangeEvent } from 'react';
import { useEffect, useId, useState } from 'react';

import { ACCEPTED_PROOF_TYPES, MAX_PROOF_BYTES } from '../config';
import { formatBytes } from '../lib/format';

interface ProofUploadProps {
  file: File | null;
  error?: string | null;
  /** Reports the file and, when the file is unusable, the reason. The parent
   *  keeps both so that submit-time validation reads from one place. */
  onChange: (file: File | null, error: string | null) => void;
}

function validate(file: File): string | null {
  if (file.size > MAX_PROOF_BYTES) {
    return `That file is ${formatBytes(file.size)}. Please choose one under 5 MB.`;
  }
  if (file.size === 0) return 'That file appears to be empty. Please choose another.';
  // Some Android camera apps report an empty or odd MIME type, so the extension
  // is accepted as a fallback rather than rejecting a genuine bill photo.
  const byType = ACCEPTED_PROOF_TYPES.includes(file.type);
  const byName = /\.(jpe?g|png|webp|heic|pdf)$/i.test(file.name);
  if (!byType && !byName) return 'Please upload a photo (JPG, PNG) or a PDF.';
  return null;
}

export function ProofUpload({ file, error, onChange }: ProofUploadProps) {
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file || !file.type.startsWith('image/')) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    // Object URLs pin the whole file in memory until revoked, which on a phone
    // with a 4 MB photo is worth caring about.
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function handleSelect(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    if (!selected) {
      onChange(null, null);
      return;
    }
    onChange(selected, validate(selected));
    // Reset so re-picking the same file after an error still fires a change.
    event.target.value = '';
  }

  return (
    <div className={`field${error ? ' field--invalid' : ''}`}>
      {/* Same rule as Field.tsx: the hint describes, it does not name. */}
      <span className="field__label" id={`${inputId}-label`}>
        Photo of your bill or invoice
      </span>
      <p className="field__hint" id={`${inputId}-hint`}>
        A clear photo of the receipt, or a PDF. Up to 5 MB. This is how GoodBed checks when you
        bought the mattress.
      </p>

      <div className="upload">
        <input
          id={inputId}
          className="upload__input"
          type="file"
          accept="image/*,application/pdf"
          onChange={handleSelect}
          aria-labelledby={`${inputId}-label`}
          aria-describedby={[`${inputId}-hint`, error ? errorId : null].filter(Boolean).join(' ')}
          aria-invalid={error ? true : undefined}
        />

        {file ? (
          <div className="preview">
            {previewUrl ? (
              <img className="preview__thumb" src={previewUrl} alt="" />
            ) : (
              <div className="preview__thumb preview__doc">PDF</div>
            )}
            <div className="preview__meta">
              <div className="preview__name">{file.name}</div>
              <div className="preview__size">{formatBytes(file.size)}</div>
            </div>
            <button
              type="button"
              className="preview__remove"
              onClick={() => onChange(null, null)}
            >
              Remove
            </button>
          </div>
        ) : (
          <label className="upload__button" htmlFor={inputId}>
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
              <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
            </svg>
            Choose photo or PDF
          </label>
        )}
      </div>

      {file && !error ? (
        <p className="field__hint" style={{ marginTop: '0.5rem', marginBottom: 0 }}>
          Tap Remove if you picked the wrong file.
        </p>
      ) : null}

      {error ? (
        <p className="field__error" id={errorId}>
          <span aria-hidden="true">!</span>
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}
