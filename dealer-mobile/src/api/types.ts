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
  stock: number | null;
  is_active: boolean;
  sort_order: number;
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
