import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosAdapter } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiResponseError, api, apiErrorMessage, extractApiError } from './client';

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

/**
 * The deploy failure this guards: all three front ends share one Vercel origin
 * whose catch-all rewrite answers any unknown path with index.html, 200
 * text/html. If VITE_API_BASE_URL is unset (the default is the literal
 * 'http://localhost:8000') or pointed at the panel itself, every API call gets
 * the SPA shell back. axios does not throw on that — silentJSONParsing swallows
 * the parse failure and hands the HTML through as `data`, so the login screen
 * used to "succeed" and store the string "undefined" as the access token.
 */
const SPA_SHELL = '<!doctype html><html><body>GB Rewards</body></html>';

function fixedAdapter(data: unknown, contentType: string, status = 200): AxiosAdapter {
  return async (config) => ({
    data,
    status,
    statusText: 'OK',
    headers: new AxiosHeaders({ 'content-type': contentType }),
    config,
  });
}

describe('non-JSON 200', () => {
  const originalAdapter = api.defaults.adapter;

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    vi.restoreAllMocks();
  });

  it('rejects an HTML 200 with an actionable invalid_response error', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.defaults.adapter = fixedAdapter(SPA_SHELL, 'text/html; charset=utf-8');

    const outcome = await api.get('/admin/products').then(
      (resp) => ({ rejected: false as const, data: resp.data as unknown }),
      (e: unknown) => ({ rejected: true as const, error: e }),
    );

    // Before the guard this RESOLVED, handing the caller a string of HTML.
    expect(outcome).toMatchObject({ rejected: true });
    const error = outcome.rejected ? outcome.error : null;
    expect(error).toBeInstanceOf(ApiResponseError);
    expect(extractApiError(error)?.code).toBe('invalid_response');
    // The diagnosis names the content type and the culprit env var...
    expect((error as ApiResponseError).message).toContain('text/html');
    expect((error as ApiResponseError).message).toContain('VITE_API_BASE_URL');
    expect((error as ApiResponseError).details.contentType).toContain('text/html');
    expect(consoleError).toHaveBeenCalled();
    // ...and the operator gets an instruction, not "Something went wrong".
    expect(apiErrorMessage(error, 'Login failed')).toContain('VITE_API_BASE_URL');
    expect(apiErrorMessage(error, 'Login failed')).not.toBe('Login failed');
  });

  it('lets a real JSON 200 through untouched', async () => {
    api.defaults.adapter = fixedAdapter({ items: [], total: 0 }, 'application/json');

    const resp = await api.get('/admin/products');

    expect(resp.data).toEqual({ items: [], total: 0 });
  });

  it('lets a blob download through — a QR sheet PDF is not JSON by design', async () => {
    api.defaults.adapter = fixedAdapter(new Blob(['%PDF-1.4']), 'application/pdf');

    const resp = await api.get('/admin/batches/abc/export', { responseType: 'blob' });

    expect(resp.data).toBeInstanceOf(Blob);
  });
});
