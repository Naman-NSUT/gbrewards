import { api, ApiRequestError } from './client';

/**
 * The invoice behind a self-registration.
 *
 * Fetched as a blob rather than pointed at with an <img src>: the endpoint is
 * admin-authenticated, and the browser sends no Authorization header on an
 * image request. The bytes come back through the same axios instance as
 * everything else, so the token — and its refresh-on-401 — apply here too.
 */
export interface Proof {
  url: string;
  contentType: string;
}

/**
 * The two 404s mean opposite things to an approver:
 *
 *   no_proof      — nothing was ever attached. Normal for a backdate request.
 *   proof_missing — the row says there IS an invoice and the file is gone.
 *
 * Reading the second as the first would let someone reject a genuine warranty
 * because the evidence looked absent rather than lost.
 */
const MESSAGES: Record<string, string> = {
  no_proof: 'No invoice was attached to this registration.',
  proof_missing:
    'This registration records an invoice, but the file could not be read. ' +
    'Do not reject on that basis — the evidence is lost, not absent.',
  warranty_not_found: 'That registration no longer exists.',
};

/**
 * Returns an object URL the caller MUST revoke when it stops showing it —
 * otherwise the invoice stays in memory for the life of the tab, which for a
 * queue worked all day is every invoice they looked at.
 */
export async function fetchProof(warrantyId: string): Promise<Proof> {
  const resp = await api.get(`/dealer-admin/warranties/${warrantyId}/proof`, {
    responseType: 'blob',
    // 404 is an ANSWER here, not a failure: which of the two 404s came back is
    // the whole signal. Letting it reach the shared error interceptor would
    // lose it — that path reads the code off a parsed JSON body, and with
    // responseType 'blob' the body is bytes, so every 404 arrives as a generic
    // http_error. Everything else (401 above all, whose refresh-and-retry lives
    // in that interceptor) is deliberately left to fail normally.
    validateStatus: (status) => status === 200 || status === 404,
  });

  const blob = resp.data as Blob;

  if (resp.status === 404) {
    let code = 'no_proof';
    try {
      const parsed: unknown = JSON.parse(await blob.text());
      const found = (parsed as { error?: { code?: unknown } })?.error?.code;
      if (typeof found === 'string') code = found;
    } catch {
      // Body was not the JSON envelope. Fall back to the benign reading rather
      // than inventing a scarier one.
    }
    throw new ApiRequestError(code, MESSAGES[code] ?? 'Could not load the invoice', 404, {});
  }

  return { url: URL.createObjectURL(blob), contentType: blob.type };
}
