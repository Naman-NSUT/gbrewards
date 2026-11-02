import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { apiErrorMessage } from './client';

/**
 * What the operator reads when a save fails.
 *
 * Every FastAPI validation failure carries the same sentence — "Request
 * validation failed" — so showing the message alone makes a missing image and an
 * unreadable number look like the same problem. The field name is the whole
 * point of the error.
 */
function axios422(errors: unknown[]): AxiosError {
  const err = new AxiosError('Request failed with status code 422');
  err.response = {
    status: 422,
    statusText: 'Unprocessable Entity',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: {
      error: {
        code: 'validation_error',
        message: 'Request validation failed',
        details: { errors },
      },
    },
  };
  return err;
}

describe('apiErrorMessage', () => {
  it('names the field a validation error objected to', () => {
    const msg = apiErrorMessage(
      axios422([
        { type: 'int_parsing', loc: ['body', 'sort_order'], msg: 'Input should be a valid integer' },
      ]),
    );

    expect(msg).toContain('sort_order');
    expect(msg).toContain('valid integer');
    // The generic sentence on its own told the operator nothing.
    expect(msg).not.toBe('Request validation failed');
  });

  it('lists every field when more than one is wrong', () => {
    const msg = apiErrorMessage(
      axios422([
        { loc: ['body', 'image'], msg: 'Field required' },
        { loc: ['body', 'sort_order'], msg: 'Input should be a valid integer' },
      ]),
    );

    expect(msg).toContain('image');
    expect(msg).toContain('sort_order');
  });

  it('falls back to the plain message when there is no field detail', () => {
    expect(apiErrorMessage(axios422([]))).toBe('Request validation failed');
  });

  it('leaves non-validation errors exactly as the server worded them', () => {
    const err = new AxiosError('boom');
    err.response = {
      status: 413,
      statusText: 'Payload Too Large',
      headers: {},
      config: { headers: new AxiosHeaders() },
      data: {
        error: {
          code: 'image_too_large',
          message: 'Image exceeds the 15 MB upload limit',
          details: {},
        },
      },
    };

    expect(apiErrorMessage(err)).toBe('Image exceeds the 15 MB upload limit');
  });

  it('uses the caller fallback when the error is not ours at all', () => {
    expect(apiErrorMessage(new Error('network down'), 'Could not save banner')).toBe(
      'Could not save banner',
    );
  });
});
