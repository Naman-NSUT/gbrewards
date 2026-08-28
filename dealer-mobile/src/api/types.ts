// Mirrors backend/app/schemas/*. Field names are snake_case because they are the
// wire format; converting them would only add a layer that can disagree.

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface StaffOut {
  id: string;
  name: string;
  phone: string;
  role: 'owner' | 'staff';
}

export interface DealerBrief {
  id: string;
  code: string;
  name: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  staff: StaffOut | null;
  dealer: DealerBrief | null;
}

/** Warranty statuses the backend can store. `expired` is derived, never stored. */
export type WarrantyStatus =
  | 'pending_confirmation'
  | 'pending_review'
  | 'pending_backdate'
  | 'active'
  | 'claimed'
  | 'voided';

export interface CustomerBrief {
  name: string;
  phone: string;
}

export interface WarrantyOut {
  id: string;
  serial: string;
  model_name: string | null;
  warranty_months: number;
  warranty_start_date: string; // ISO yyyy-mm-dd
  warranty_end_date: string; // ISO yyyy-mm-dd
  status: WarrantyStatus;
  invoice_ref: string | null;
  invoice_date: string | null;
  backdate_days: number;
  unit_unverified: boolean;
  registered_at: string; // ISO datetime
  // Not returned by the list endpoint today. Rendered when present so the field
  // can be added server-side without a client change.
  customer?: CustomerBrief | null;
}

export interface UnitPreviewOut {
  serial: string;
  model_name: string | null;
  warranty_months: number;
  registerable: boolean;
  reason: string | null;
  already_registered: boolean;
}

/** Exactly the JSON body POSTed to /dealer/registrations. */
export interface RegisterBody {
  serial: string;
  customer_phone: string;
  customer_name: string;
  invoice_ref: string;
  invoice_date?: string | null; // ISO yyyy-mm-dd
  customer_address?: string | null;
  customer_city?: string | null;
  customer_state?: string | null;
  customer_pincode?: string | null;
}

export interface RegisterOut {
  warranty: WarrantyOut;
  customer: CustomerBrief;
  points_awarded: number;
  balance: number;
  idempotent: boolean;
  unit_unverified: boolean;
}

export interface PointsSummary {
  balance: number;
  pending: number;
  available: number;
  total_earned: number;
}

export type LedgerEntryType =
  | 'registration_credit'
  | 'registration_reversal'
  | 'redemption_debit'
  | 'redemption_release'
  | 'admin_credit'
  | 'admin_debit';

export interface LedgerEntryOut {
  id: string;
  amount: number;
  type: LedgerEntryType;
  reason: string | null;
  warranty_id: string | null;
  redemption_id: string | null;
  // Convenience denormalisation so the history can name the sale it paid for.
  serial?: string | null;
  created_at: string;
}

export interface RewardOut {
  id: string;
  name: string;
  description: string | null;
  points_cost: number;
  image_url: string | null;
  /**
   * The server decides these three, and the app must not recompute them.
   *
   * `affordable` is measured against the balance MINUS points already held by
   * pending requests, which is the number that actually governs whether a
   * redemption will be accepted. A client comparing a raw balance to the cost
   * offers a Redeem button the server then refuses.
   *
   * `stock`, `is_active` and `sort_order` used to be declared here and are not
   * sent by this endpoint at all — inactive and out-of-stock rewards are simply
   * absent from the catalogue, and the order is the order they arrive in.
   */
  in_stock: boolean;
  affordable: boolean;
  /** Points still needed. 0 when affordable. */
  short_by: number;
}

/**
 * GET /dealer/rewards returns the catalogue AND the balance it was priced
 * against — one request, one consistent pair. Reading affordability from here
 * rather than from a separate points call means the two can never disagree.
 */
export interface CatalogueOut {
  balance: number;
  pending: number;
  available: number;
  items: RewardOut[];
}

/** GET /dealer/ledger is a page too, and it carries the balance with it. */
export interface LedgerPage {
  total: number;
  limit: number;
  offset: number;
  balance: number;
  items: LedgerEntryOut[];
}

/** GET /dealer/redemptions is a page, not a bare array. */
export interface RedemptionPage {
  total: number;
  limit: number;
  offset: number;
  items: RedemptionOut[];
}

export type RedemptionStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'fulfilled'
  | 'cancelled';

export interface RedemptionOut {
  id: string;
  reward_id: string | null;
  reward_name: string | null;
  points: number;
  status: RedemptionStatus;
  note: string | null;
  created_at: string;
  processed_at: string | null;
}
