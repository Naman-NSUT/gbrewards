/**
 * The public API contract this site consumes.
 *
 * Every endpoint below is UNAUTHENTICATED and lives under `/api/v1/public`.
 * These types are transcribed from the backend's OpenAPI document and verified
 * against the running server — field names below are the wire names, not a
 * convenience shape. If the backend changes, this file changes with it; there
 * is no translation layer anywhere between here and the components.
 *
 *   POST /public/lookup                 { phone } XOR { serial }   (both -> 422)
 *        -> 200 LookupResponse          (empty results + message, never a 404)
 *
 *   POST /public/self-registrations     multipart/form-data
 *        fields: serial, customer_phone, customer_name, purchase_date, proof(file),
 *                invoice_ref?, dealer_hint?, customer_address?, customer_city?,
 *                customer_state?, customer_pincode?
 *        -> 201 SelfRegistrationResponse   (status 'submitted')
 *        -> 200 SelfRegistrationResponse   (status 'already_registered')
 *
 *   POST /public/claims                 { serial, phone, issue_type?, description }
 *        -> 201 ClaimResponse           (200 when it re-surfaces an open claim)
 *        -> 404 not_found               (serial + phone did not match a warranty)
 *
 *   POST /public/claims/status          { reference, phone }
 *        -> 200 ClaimResponse
 *        -> 404 not_found
 *
 *   GET  /public/w/{id}?last4=NNNN      -> 200 WarrantyView
 *   POST /public/w/{id}/confirm         { last4 }        -> 200 CustomerActionResponse
 *   POST /public/w/{id}/dispute         { last4, note? } -> 200 CustomerActionResponse
 *        -> 403 invalid_link            (unknown id AND wrong last4 — deliberately
 *                                        indistinguishable, so do not treat 403
 *                                        here as "no such warranty")
 *
 * Two properties of this contract the UI is built on:
 *
 * 1. Lookup takes EXACTLY ONE of phone or serial. Sending both is a 422, and so
 *    is sending neither — the server refuses to let a caller narrow a search by
 *    combining them. The single search box therefore has to decide which one it
 *    is holding before it can ask; see `classifyQuery`.
 *
 * 2. The customer on a public warranty is ALWAYS masked — "M**** I****" and
 *    "98****3210" — whichever way it was found, and the mask is fixed width so
 *    it does not leak the real length. There is no flag to check and no
 *    unmasked variant to request. The client renders what it is given.
 */

/** The stored statuses from the `status_valid` check constraint, plus `expired`,
 *  which is never stored — it is derived from the end date by the backend's
 *  `display_status()` and only ever appears on the way out. */
export type WarrantyStatus =
  | 'pending_confirmation'
  | 'pending_review'
  | 'pending_backdate'
  | 'active'
  | 'claimed'
  | 'voided'
  | 'expired';

export type WarrantySource = 'dealer' | 'customer_self' | 'admin' | 'migration';

export type ClaimStatus = 'open' | 'in_review' | 'approved' | 'rejected' | 'closed';

/** `SellingDealerOut`. Shop name and city only — the public API carries no
 *  dealer contact details, by design. */
export interface SellingDealer {
  name: string;
  city: string | null;
}

/** `MaskedCustomerOut`. Both values arrive pre-masked, always. */
export interface MaskedCustomer {
  name: string;
  phone: string;
}

/** `RedactedWarrantyOut` — the only public rendering of a warranty, shared by
 *  every endpoint on this site. */
export interface RedactedWarranty {
  id: string;
  serial: string;
  model_name: string | null;
  status: WarrantyStatus;
  warranty_months: number;
  /** ISO calendar dates (YYYY-MM-DD), in the seller's timezone, not instants. */
  warranty_start_date: string;
  warranty_end_date: string;
  registered_at: string;
  source: WarrantySource;
  customer: MaskedCustomer;
  /** Absent for a customer self-registration — nobody sold it through the system. */
  dealer: SellingDealer | null;
}

/** `LookupOut`. An empty `results` is a 200, not a 404. */
export interface LookupResponse {
  results: RedactedWarranty[];
  /** Server-authored copy for the empty case; null when there are results. */
  message: string | null;
  /** The signal for the "register it yourself" call to action. Do not infer this
   *  from `results.length` — the server decides, and it is deliberately true for
   *  an unknown serial so the flag cannot be used as an existence oracle. */
  can_self_register: boolean;
}

/** `WarrantyViewOut` — GET /public/w/{id}. */
export interface WarrantyView {
  warranty: RedactedWarranty;
  /** The warranty is sitting in `pending_confirmation` and this reply activates it. */
  awaiting_confirmation: boolean;
  /** Already confirmed, by this customer or by an earlier verification. */
  already_confirmed: boolean;
}

/** `CustomerActionOut` — the reply to confirm and dispute alike. */
export interface CustomerActionResponse {
  warranty: RedactedWarranty;
  /** Server-authored sentence shown verbatim. The outcome of a dispute is a
   *  policy decision (it queues a review, it does NOT void) and belongs to the
   *  backend, so the page never promises an outcome of its own invention. */
  message: string;
}

/** `SelfRegistrationOut.status`. */
export type SelfRegistrationStatus = 'submitted' | 'already_registered';

export interface SelfRegistrationResponse {
  status: SelfRegistrationStatus;
  /** The record — newly queued, or the existing one when it turns out the
   *  dealer registered it after all. */
  warranty: RedactedWarranty;
  message: string;
}

/** `ClaimOut` — returned by both claim creation and the status check. */
export interface ClaimResponse {
  reference: string;
  status: ClaimStatus;
  issue_type: string | null;
  description: string;
  created_at: string;
  resolution_note: string | null;
  resolved_at: string | null;
  warranty: RedactedWarranty;
  message: string;
}

/** The `{"error": {...}}` envelope every service in this product family speaks. */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
