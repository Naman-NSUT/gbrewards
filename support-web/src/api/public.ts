import { getJson, postForm, postJson } from './client';
import type {
  ClaimResponse,
  CustomerActionResponse,
  LookupResponse,
  SelfRegistrationResponse,
  WarrantyView,
} from './types';

/**
 * Exactly one of phone or serial, made unrepresentable rather than merely
 * documented: `POST /public/lookup` returns 422 if both are set AND if neither
 * is, so a shape that could carry two optional strings would put a validation
 * failure one careless call site away.
 */
export type LookupQuery = { kind: 'phone'; value: string } | { kind: 'serial'; value: string };

/**
 * A lookup that finds nothing is not an error to this product — it is the most
 * valuable answer the site can give, because it means a mattress was sold and
 * never registered. The backend agrees: an empty search is a 200 carrying its
 * own copy and a `can_self_register` flag, so the whole response is returned
 * here and the caller reads the server's signal instead of inferring one.
 */
export function lookupWarranties(query: LookupQuery): Promise<LookupResponse> {
  const body = query.kind === 'phone' ? { phone: query.value } : { serial: query.value };
  return postJson<LookupResponse>('/public/lookup', body);
}

export interface SelfRegistrationInput {
  serial: string;
  customerName: string;
  customerPhone: string;
  /** YYYY-MM-DD, from the bill. Required — recovering the real sale date is the
   *  entire point of this form. */
  purchaseDate: string;
  proof: File;
  /** The bill number, if the customer can read one off the invoice. */
  invoiceRef?: string;
  /** Which shop they bought from, in their own words. When the serial was never
   *  allocated to a dealer this is the only lead the compliance team has. */
  dealerHint?: string;
}

export function submitSelfRegistration(
  input: SelfRegistrationInput,
): Promise<SelfRegistrationResponse> {
  const form = new FormData();
  form.append('serial', input.serial);
  form.append('customer_name', input.customerName);
  form.append('customer_phone', input.customerPhone);
  form.append('purchase_date', input.purchaseDate);
  form.append('proof', input.proof, input.proof.name);
  // Omitted rather than sent empty: the server types these as `str | None`, and
  // an empty string is a value, not an absence.
  if (input.invoiceRef?.trim()) form.append('invoice_ref', input.invoiceRef.trim());
  if (input.dealerHint?.trim()) form.append('dealer_hint', input.dealerHint.trim());
  return postForm<SelfRegistrationResponse>('/public/self-registrations', form);
}

export interface ClaimInput {
  serial: string;
  phone: string;
  /** Optional on the wire (max 60 chars); the form always sends one. */
  issueType?: string;
  description: string;
}

/** 404 `not_found` when the serial and phone do not name the same warranty —
 *  the pair is the possession check, and the server will not say which half
 *  was wrong. */
export function submitClaim(input: ClaimInput): Promise<ClaimResponse> {
  return postJson<ClaimResponse>('/public/claims', {
    serial: input.serial,
    phone: input.phone,
    issue_type: input.issueType || null,
    description: input.description,
  });
}

export function lookupClaim(reference: string, phone: string): Promise<ClaimResponse> {
  return postJson<ClaimResponse>('/public/claims/status', { reference, phone });
}

/**
 * The possession check behind the SMS link: prove you hold the phone the
 * warranty was registered to before you see or change anything.
 *
 * This one is a GET with `last4` in the query string — the only customer
 * identifier this site ever puts in a URL, and the backend's choice. Wrong
 * digits and an unknown id both return 403 `invalid_link`, on purpose: the
 * error must not reveal whether a guessed warranty id exists.
 */
export function viewWarranty(warrantyId: string, last4: string): Promise<WarrantyView> {
  const query = new URLSearchParams({ last4 });
  return getJson<WarrantyView>(`/public/w/${encodeURIComponent(warrantyId)}?${query}`);
}

export function confirmWarranty(
  warrantyId: string,
  last4: string,
): Promise<CustomerActionResponse> {
  return postJson<CustomerActionResponse>(`/public/w/${encodeURIComponent(warrantyId)}/confirm`, {
    last4,
  });
}

/** `note` is free text, capped at 1000 characters server-side. A dispute never
 *  voids the warranty — it records the customer's word and queues a human. */
export function disputeWarranty(
  warrantyId: string,
  last4: string,
  note?: string,
): Promise<CustomerActionResponse> {
  return postJson<CustomerActionResponse>(`/public/w/${encodeURIComponent(warrantyId)}/dispute`, {
    last4,
    note: note?.trim() ? note.trim().slice(0, 1000) : null,
  });
}
