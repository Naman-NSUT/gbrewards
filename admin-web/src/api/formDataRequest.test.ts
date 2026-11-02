import type { InternalAxiosRequestConfig } from 'axios';
import axios, { AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { api } from './client';

/**
 * A banner upload has to leave the browser as multipart.
 *
 * This instance sets a JSON content-type for every request, and axios reads that
 * back in transformRequest: FormData sent with a JSON content-type is converted
 * with `JSON.stringify(formDataToJSON(data))` instead of being sent as multipart.
 * A File has no JSON representation, so the image became `{}` and the server
 * rejected the request as missing every field — a 422 that pointed at the form
 * rather than at the transport.
 *
 * These run the real axios transform rather than asserting on our own code, so
 * they would also catch axios changing this behaviour under us.
 */
function runInterceptor(data: unknown): InternalAxiosRequestConfig {
  const config = {
    headers: new AxiosHeaders({ 'Content-Type': 'application/json' }),
    data,
    method: 'post',
    url: '/admin/banners',
  } as unknown as InternalAxiosRequestConfig;

  // The instance's own request interceptor, whatever it happens to be.
  const handler = (
    api.interceptors.request as unknown as {
      handlers: { fulfilled: (c: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }[];
    }
  ).handlers[0];
  return handler.fulfilled(config);
}

function transform(config: InternalAxiosRequestConfig): unknown {
  const t = axios.defaults.transformRequest as unknown as ((
    d: unknown,
    h: AxiosHeaders,
  ) => unknown)[];
  return t[0](config.data, config.headers as AxiosHeaders);
}

describe('FormData requests', () => {
  it('does not leave a JSON content-type on a multipart body', () => {
    const fd = new FormData();
    fd.append('image', new File(['x'], 'banner.png', { type: 'image/png' }));

    const config = runInterceptor(fd);

    expect(config.headers.getContentType()).toBeFalsy();
  });

  it('survives axios transformRequest as FormData, not as JSON', () => {
    const fd = new FormData();
    fd.append('image', new File(['x'], 'banner.png', { type: 'image/png' }));
    fd.append('caption', 'Happy Diwali');

    const body = transform(runInterceptor(fd));

    // The whole bug in one assertion: a string here means the file was dropped.
    expect(typeof body).not.toBe('string');
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get('image')).toBeInstanceOf(File);
  });

  it('shows what went wrong before: JSON content-type eats the file', () => {
    const fd = new FormData();
    fd.append('image', new File(['x'], 'banner.png', { type: 'image/png' }));

    // Skip the interceptor — this is the old behaviour.
    const body = transform({
      headers: new AxiosHeaders({ 'Content-Type': 'application/json' }),
      data: fd,
    } as unknown as InternalAxiosRequestConfig);

    expect(typeof body).toBe('string');
    // The File serialises to nothing a server can read as an upload.
    expect(JSON.parse(body as string).image).not.toBeInstanceOf(File);
  });

  it('leaves an ordinary JSON request alone', () => {
    const config = runInterceptor({ email: 'a@b.c', password: 'x' });

    expect(config.headers.getContentType()).toContain('application/json');
  });
});
