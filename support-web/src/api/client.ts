/**
 * Minimal fetch wrapper around the `{"error": {code, message, details}}` envelope.
 *
 * No axios, no react-query: this app makes at most one request per screen and
 * has no auth to refresh. A HTTP client and a cache layer would be most of the
 * bundle for a page whose job is to load fast on a bad connection.
 */

import { API_BASE_URL, API_PREFIX, REQUEST_TIMEOUT_MS } from '../config';
import type { ApiErrorBody } from './types';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(code: string, status: number, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** True when the server definitively said "no such thing", as opposed to
   *  failing. The lookup screens turn this into the registration CTA rather
   *  than into an error. */
  get isNotFound(): boolean {
    return this.status === 404 || this.code === 'not_found';
  }
}

/**
 * A 200 that is not JSON, explained instead of thrown away.
 *
 * All three front ends ship from ONE Vercel origin, and the last rule in the
 * root vercel.json is `{"source": "/(.*)", "destination": "/index.html"}` — any
 * path that is not a built asset answers 200 text/html with a SPA shell. This
 * site's API_BASE_URL defaults to '' ("same origin"), so a deploy that forgets
 * VITE_API_BASE_URL sends every request into that catch-all and gets this very
 * page back: `response.ok` is true and the body is HTML.
 *
 * The unguarded `response.json()` this replaced threw a raw SyntaxError. A
 * SyntaxError is not an ApiError, so friendlyMessage() failed its instanceof
 * check and every screen showed "Something went wrong. Please try again." — the
 * one sentence that gives nobody, customer or engineer, anything to act on.
 */
function invalidResponse(response: Response, body: string): ApiError {
  const contentType = response.headers.get('content-type') ?? 'unknown';
  const diagnosis =
    `Expected JSON from ${response.url || 'the API'} but got ${contentType} ` +
    `(HTTP ${response.status}). VITE_API_BASE_URL is probably unset or pointing at ` +
    `this site instead of the API, so the site's own index.html came back.`;
  // The customer gets the sentence in friendlyMessage(); the console keeps the
  // diagnosis, because this is a deploy fault and only an engineer can fix it.
  console.error(`[api] ${diagnosis}`, body.slice(0, 200));
  return new ApiError('invalid_response', response.status, diagnosis, { contentType });
}

async function parseError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // A gateway timeout or a proxy error page is not JSON. Fall through.
  }
  const envelope = (body as { error?: ApiErrorBody } | null)?.error;
  if (envelope?.code) {
    return new ApiError(
      envelope.code,
      response.status,
      envelope.message || 'Something went wrong',
      envelope.details ?? {},
    );
  }
  return new ApiError('http_error', response.status, `Request failed (${response.status})`);
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, {
      ...init,
      signal: controller.signal,
    });
  } catch (cause) {
    // A dropped connection and a deliberate abort are indistinguishable to the
    // customer, and both mean "we could not ask". Say that, don't leak DOMException.
    const aborted = cause instanceof DOMException && cause.name === 'AbortError';
    throw new ApiError(
      aborted ? 'timeout' : 'network_error',
      0,
      aborted ? 'The request took too long' : 'Could not reach the server',
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;

  // Read as text and parse here rather than calling response.json(), so a body
  // that is not JSON leaves as an ApiError the UI understands. See invalidResponse.
  const body = await response.text();
  try {
    return JSON.parse(body) as T;
  } catch {
    throw invalidResponse(response, body);
  }
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' });
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function postForm<T>(path: string, form: FormData): Promise<T> {
  // Content-Type is deliberately unset: the browser must add the multipart
  // boundary itself, and setting it by hand silently breaks the upload.
  return request<T>(path, { method: 'POST', body: form });
}

/**
 * Turn any failure into a sentence a customer can act on.
 *
 * The server's own message is preferred — it is written by the people who know
 * why the rule exists — except where the server message is written for an
 * operator rather than a buyer. "Too many requests, slow down" is correct and
 * useless to someone who has typed their phone number three times.
 */
export function friendlyMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (!(error instanceof ApiError)) return fallback;

  switch (error.code) {
    case 'network_error':
      return 'We could not reach GoodBed. Check your internet connection and try again.';
    case 'timeout':
      return 'That took too long. Your connection may be slow — please try again.';
    case 'rate_limited':
      return 'You have tried a few times in quick succession. Please wait a minute and try again.';
    case 'rate_limit_unavailable':
      return 'Our service is busy right now. Please try again in a minute.';
    case 'invalid_response':
      // A misconfigured deploy, not anything the customer did or can retry away.
      // Say so plainly and point at the phone number rather than inviting a
      // fourth attempt at a form that cannot possibly submit.
      return (
        'This page cannot reach GoodBed right now. Please try again later, or contact ' +
        'GoodBed support if it keeps happening.'
      );
    case 'validation_error':
      return firstValidationMessage(error) ?? 'Please check the details you entered.';
    default:
      break;
  }

  if (error.status === 429) {
    return 'You have tried a few times in quick succession. Please wait a minute and try again.';
  }
  if (error.status === 413) {
    return 'That file is too large to upload. Please use a photo under 5 MB.';
  }
  if (error.status >= 500) {
    return 'Something went wrong at our end. Please try again in a few minutes.';
  }
  return error.message || fallback;
}

/**
 * The backend puts Pydantic's errors under `details.errors` as `{loc, msg, type}`,
 * verified against the live server. The first message is almost always the one
 * the customer can fix.
 *
 * Pydantic prefixes messages raised by a model validator with "Value error, ";
 * that prefix names the mechanism, not the problem, so it is dropped before the
 * sentence reaches a customer.
 */
function firstValidationMessage(error: ApiError): string | null {
  const errors = error.details?.errors;
  if (!Array.isArray(errors) || errors.length === 0) return null;
  const msg = (errors[0] as { msg?: unknown }).msg;
  if (typeof msg !== 'string' || !msg.trim()) return null;
  return msg.replace(/^value error,\s*/i, '').trim() || null;
}
