/**
 * The admin API contract, mirrored from backend/app/schemas/admin.py.
 *
 * Field names are snake_case because the API is, and translating at the boundary
 * would mean every bug report quotes a name that appears nowhere in the backend.
 *
 * Pagination is offset/total, not cursor. Admin screens sort worst-first and the
 * client asks "how many dealers are below 50%?" — a cursor feed can answer
 * neither. The dealer app's feeds can stay cursor-based; these are tables.
 */

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

/** `Paginated_X_` on the server: every list endpoint returns exactly this. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Ok {
  ok: boolean;
}

// ---------------------------------------------------------------- auth ------

export type AdminRole = 'owner' | 'staff' | 'support';

/** GET /admin/me */
export interface AdminProfile {
  id: string;
  email: string;
  name: string;
  role: AdminRole;
}

/** The admin login/refresh pair. `staff`/`dealer` are only filled for dealer
 *  tokens, so this panel never reads them. */
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

// ------------------------------------------------------------- shared -------

export interface DealerBrief {
  id: string;
  code: string;
  name: string;
  status: string;
  city?: string | null;
}

export interface CustomerBrief {
  id: string;
  name: string;
  phone: string;
}

/** CustomerOut — note there is no `created_at` on the admin customer. */
export interface Customer extends CustomerBrief {
  email: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  is_phone_verified: boolean;
}

export interface StaffBrief {
  id: string;
  name: string;
  phone: string;
  role: string;
}

export type WarrantyStatus =
  | 'pending_confirmation'
  | 'pending_review'
  | 'pending_backdate'
  | 'active'
  | 'claimed'
  | 'voided';

/** What `WarrantyListItem.status` carries: the stored status with expiry folded
 *  in. The raw column is `stored_status`. */
export type WarrantyDisplayStatus = WarrantyStatus | 'expired';

export type WarrantySource = 'dealer' | 'customer_self' | 'admin' | 'migration';

/** WarrantyListItem. `status` is display status; `stored_status` is the column. */
export interface WarrantyListItem {
  id: string;
  serial: string;
  model_name: string | null;
  model_code: string | null;
  status: WarrantyDisplayStatus;
  stored_status: WarrantyStatus;
  source: WarrantySource;
  warranty_months: number;
  warranty_start_date: string;
  warranty_end_date: string;
  backdate_days: number;
  unit_unverified: boolean;
  invoice_ref: string | null;
  invoice_date: string | null;
  registered_at: string;
  customer?: CustomerBrief | null;
  dealer?: DealerBrief | null;
}

export interface WarrantyEvent {
  id: string;
  warranty_id: string;
  event: string;
  from_status: string | null;
  to_status: string | null;
  actor_type: string;
  actor_id: string | null;
  actor_name?: string | null;
  reason: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export type LedgerType =
  | 'registration_credit'
  | 'registration_reversal'
  | 'redemption_debit'
  | 'redemption_release'
  | 'admin_credit'
  | 'admin_debit';

/** LedgerEntryOut. The server sends ids, not names — anything human-readable
 *  about the cause lives in `metadata` (e.g. `metadata.serial`). */
export interface LedgerEntry {
  id: string;
  dealer_id: string;
  amount: number;
  type: LedgerType;
  warranty_id: string | null;
  redemption_id: string | null;
  rate_version_id: string | null;
  admin_id: string | null;
  staff_id: string | null;
  reason: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  balance_after?: number | null;
}

export interface ClaimBrief {
  id: string;
  reference: string;
  status: ClaimStatus;
  issue_type: string | null;
  created_at: string;
}

/** WarrantyDetailOut — a wrapper, not a flattened row. */
export interface WarrantyDetail {
  warranty: WarrantyListItem;
  is_expired: boolean;
  customer: Customer;
  dealer: DealerBrief | null;
  staff: StaffBrief | null;
  events: WarrantyEvent[];
  ledger_entries: LedgerEntry[];
  claims: ClaimBrief[];
  void_reason?: string | null;
  voided_at?: string | null;
  proof_file_key?: string | null;
}

// ---------------------------------------------------------- dashboard -------

/** GET /admin/dashboard */
export interface DashboardStats {
  today: string;
  registered_today: number;
  registered_this_month: number;
  self_registered_this_month: number;
  active_warranties: number;
  active_dealers: number;
  pending_approvals: number;
  open_claims: number;
  unverified_units: number;
  points_issued: number;
  points_reversed: number;
}

export interface RegistrationDayPoint {
  date: string;
  dealer: number;
  customer_self: number;
}

/** GET /admin/dashboard/analytics?days=N */
export interface DashboardAnalytics {
  days: number;
  series: RegistrationDayPoint[];
}

// --------------------------------------------------------- compliance -------

/** ComplianceRowOut. Stock is not scoped to shops, so there is no allocated-vs-
 *  registered ratio: the signal is self_registrations (a customer had to do it
 *  themselves) and how long a shop has been quiet. */
export interface ComplianceRow {
  dealer_id: string;
  dealer_code: string;
  dealer_name: string;
  city: string | null;
  dealer_status: string;
  warranties_registered: number;
  /** Warranties on this dealer's serials that the CUSTOMER registered, not them. */
  self_registrations: number;
  backdated_registrations: number;
  last_registration_at: string | null;
  days_since_last_registration: number | null;
  non_compliance_score: number;
}

export interface ComplianceTotals {
  dealers: number;
  warranties_registered: number;
  self_registrations: number;
}

/** ComplianceOut — paginated, plus the window it was computed over. */
export interface CompliancePage extends Page<ComplianceRow> {
  date_from: string | null;
  date_to: string | null;
  sort: string;
  totals: ComplianceTotals;
}

export interface SelfRegistration {
  warranty_id: string;
  serial: string;
  status: string;
  registered_at: string;
  invoice_date: string | null;
  proof_file_key: string | null;
  customer: CustomerBrief;
}

export interface StaffActivity {
  staff: StaffBrief;
  is_active: boolean;
  last_active_at: string | null;
  registrations: number;
}

/** DealerComplianceDetailOut */
export interface ComplianceDetail {
  dealer: DealerBrief;
  summary: ComplianceRow;
  date_from: string | null;
  date_to: string | null;
  self_registrations: SelfRegistration[];
  staff_activity: StaffActivity[];
}

// ---------------------------------------------------------- approvals -------

/** The queue is keyed on warranty status, not on a separate "kind". */
export type ApprovalStatus = 'pending_backdate' | 'pending_review';

/** ApprovalItem — `id` IS the warranty id. */
export interface ApprovalItem {
  id: string;
  serial: string;
  model_name: string | null;
  status: ApprovalStatus;
  source: WarrantySource;
  warranty_months: number;
  warranty_start_date: string;
  warranty_end_date: string;
  invoice_ref: string | null;
  /** The date the dealer asked the clock to start from. */
  requested_invoice_date: string | null;
  days_back: number;
  registered_at: string;
  waiting_days: number;
  unit_unverified: boolean;
  /** Object-store key for a self-registration's proof, not a fetchable URL. */
  proof_file_key: string | null;
  customer: CustomerBrief;
  dealer: DealerBrief | null;
  dealer_source: string | null;
  staff: StaffBrief | null;
}

/** GET /admin/approvals/count */
export interface ApprovalCounts {
  pending_backdate: number;
  pending_review: number;
  total: number;
}

// -------------------------------------------------------------- units ------

/** UnitOut. Everything but `known` and `serial` is absent on a miss. */
export interface UnitInfo {
  known: boolean;
  serial: string;
  model_name?: string | null;
  model_code?: string | null;
  warranty_months?: number | null;
  source?: string | null;
  source_status?: string | null;
  source_synced_at?: string | null;
  /** True when the row was invented by an allocation upload, not confirmed. */
  unverified?: boolean;
  /** True when the mirror row is older than UNIT_MIRROR_STALENESS_HOURS. */
  stale?: boolean;
}

/** SerialLookupOut. There is no `found` flag — `unit.known` plus the empty
 *  collections are the answer. */
export interface SerialLookup {
  serial: string;
  unit: UnitInfo;
  current_warranty: WarrantyDetail | null;
  warranties: WarrantyListItem[];
  claims: ClaimListItem[];
  sms: SmsRow[];
  events: WarrantyEvent[];
}

// ------------------------------------------------------------- claims ------

export type ClaimStatus = 'open' | 'in_review' | 'approved' | 'rejected' | 'closed';

/** ClaimListItem — the warranty is flattened onto the row, not nested. */
export interface ClaimListItem {
  id: string;
  reference: string;
  status: ClaimStatus;
  issue_type: string | null;
  description: string;
  warranty_id: string;
  serial: string;
  model_name: string | null;
  customer: CustomerBrief;
  dealer: DealerBrief | null;
  warranty_end_date: string;
  in_warranty: boolean;
  handled_by_admin_id: string | null;
  resolved_at: string | null;
  created_at: string;
}

/** ClaimDetailOut — the only place `resolution_note` is returned. */
export interface ClaimDetail {
  claim: ClaimListItem;
  resolution_note: string | null;
  warranty: WarrantyListItem;
  customer: Customer;
}

// -------------------------------------------------------- allocations ------

export type AllocationStatus = 'allocated' | 'registered' | 'revoked' | 'returned';

/** AllocationOut — the dealer is flattened onto the row as id/code/name. */
/**
 * AllocationUploadOut — returned by BOTH /allocations/preview (dry run) and
 * /allocations/upload (commit), so the review step and the result step read the
 * same numbers. There is no reassignment: a serial held by another dealer is an
 * error row, never a silent move.
 */
export interface AllocationUploadResult {
  /** New allocation rows. */
  created_count: number;
  /** Rows already allocated to this same dealer — a safe re-upload. */
  unchanged_count: number;
  /** Serials with no unit record, for which a stub was written. */
  units_stubbed: number;
}

// ------------------------------------------------------------ dealers ------

/**
 * 'pending' is where EVERY self-signed-up shop starts, so it cannot be left out
 * — omitting it made the panel unable to tell a shop awaiting verification from
 * one that had been suspended, and offered it a "Reactivate" button for a state
 * it had never been in. Mirrors the CHECK constraint on dealers.status.
 */
export type DealerStatus = 'pending' | 'active' | 'suspended' | 'closed';

/** DealerOut — the plain dealer record, with no derived counters. */
export interface Dealer {
  id: string;
  code: string;
  name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  gst_number: string | null;
  status: DealerStatus;
  created_at: string;
}

/** DealerListItem — the list row adds exactly two derived numbers. */
export interface DealerListItem extends Dealer {
  staff_count: number;
  points_balance: number;
}

export interface DealerStats {
  warranties_registered: number;
  warranties_voided: number;
  self_registrations: number;
  last_registration_at: string | null;
}

/** PointsSummaryOut — a dealer's balance, everywhere it appears. */
export interface PointsSummary {
  balance: number;
  pending: number;
  available: number;
  total_earned: number;
}

/** DealerDetailOut */
export interface DealerDetail {
  dealer: Dealer;
  staff: StaffRow[];
  points: PointsSummary;
  stats: DealerStats;
}

export interface DealerInput {
  code: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  pincode?: string | null;
  gst_number?: string | null;
}

/** StaffOut — no per-staff registration counter here; that lives on the
 *  compliance drilldown as `staff_activity[].registrations`. */
export interface StaffRow {
  id: string;
  dealer_id: string;
  name: string;
  phone: string;
  role: string;
  is_active: boolean;
  last_active_at: string | null;
  created_at: string;
}

export interface StaffInput {
  name: string;
  phone: string;
  role?: string;
}

/** DealerLedgerOut — a page of entries plus the dealer and their balance. */
export interface DealerLedger extends Page<LedgerEntry> {
  dealer: DealerBrief;
  points: PointsSummary;
}

/** AdjustPointsOut */
export interface AdjustResult {
  entry: LedgerEntry;
  points: PointsSummary;
}

// ------------------------------------------------------------ rewards ------

export interface RewardRow {
  id: string;
  name: string;
  description: string | null;
  points_cost: number;
  image_url: string | null;
  stock: number | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface RewardInput {
  name: string;
  description?: string | null;
  points_cost: number;
  image_url?: string | null;
  stock?: number | null;
  is_active?: boolean;
  sort_order?: number;
}

export type RedemptionStatus = 'pending' | 'approved' | 'rejected' | 'fulfilled' | 'cancelled';

/** RedemptionOut — the requester is a staff brief; the processor is an id only. */
export interface RedemptionRow {
  id: string;
  dealer: DealerBrief;
  requested_by: StaffBrief | null;
  reward_id: string | null;
  reward_name: string | null;
  points: number;
  status: RedemptionStatus;
  note: string | null;
  processed_by_admin_id: string | null;
  processed_at: string | null;
  created_at: string;
}

/** RedemptionDecisionOut — the decision plus the balance it left behind. */
export interface RedemptionDecision {
  redemption: RedemptionRow;
  points: PointsSummary;
}

// ---------------------------------------------------------------- sms ------

export type SmsStatus = 'queued' | 'sent' | 'failed' | 'delivered' | 'undelivered';

export interface SmsRow {
  id: string;
  to_phone: string;
  template_key: string;
  provider: string;
  provider_template_id: string | null;
  provider_message_id: string | null;
  variables: Record<string, unknown> | null;
  status: SmsStatus;
  error: string | null;
  attempts: number;
  warranty_id: string | null;
  created_at: string;
  sent_at: string | null;
  delivered_at: string | null;
  /** The rendered body, when the provider stub keeps one. */
  preview?: string | null;
}

/** GET /admin/sms/templates */
export interface SmsTemplate {
  body: string;
  variables: string[];
}

export type SmsTemplates = Record<string, SmsTemplate>;

// ------------------------------------------------------------- points ------

/** PointRateOut — versions are immutable; `created_by_admin_id` is an id. */
/** A product and what registering it currently pays a dealer. */
export interface ProductRateRow {
  product_id: string;
  product_name: string;
  is_active: boolean;
  warranty_months: number | null;
  /** null when no rate has been set — the row an admin needs to act on. */
  points_per_registration: number | null;
  rate_id: string | null;
  effective_from: string | null;
}

export interface PointRateRow {
  product_id: string;
  id: string;
  points_per_registration: number;
  effective_from: string;
  effective_to: string | null;
  note: string | null;
  created_by_admin_id: string | null;
  is_current?: boolean;
}

// -------------------------------------------------------------- audit ------

export type ActorType = 'admin' | 'dealer_staff' | 'customer' | 'system';

export interface AuditRow {
  id: string;
  actor_type: ActorType;
  actor_id: string | null;
  actor_name: string | null;
  actor_label: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  reason: string | null;
  metadata: Record<string, unknown> | null;
  ip: string | null;
  created_at: string;
}

/** GET /admin/audit/filters — the dropdown options, not part of the page. */
export interface AuditFilters {
  actions: string[];
  entity_types: string[];
}
