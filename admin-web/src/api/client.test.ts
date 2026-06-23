import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { apiErrorMessage, extractApiError } from './client';

function makeAxiosError(payload: unknown, status = 400): AxiosError {
  const err = new AxiosError('Request failed', 'ERR_BAD_REQUEST');
  err.response = {
    data: payload,
    status,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() },
  };
  return err;
}

describe('extractApiError / apiErrorMessage', () => {
  it('extracts the backend error envelope', () => {
    const err = makeAxiosError({
      error: { code: 'insufficient_balance', message: 'Not enough points', details: {} },
    });
    expect(extractApiError(err)?.code).toBe('insufficient_balance');
    expect(apiErrorMessage(err)).toBe('Not enough points');
  });

  it('falls back for non-axios errors', () => {
    expect(extractApiError(new Error('boom'))).toBeNull();
    expect(apiErrorMessage(new Error('boom'), 'fallback')).toBe('fallback');
  });
});
