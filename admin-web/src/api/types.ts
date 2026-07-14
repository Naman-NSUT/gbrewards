export interface Admin {
  id: string;
  email: string;
  name: string | null;
  role: string;
}

export interface AdminTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  admin: Admin;
}

export interface Product {
  id: string;
  name: string;
  description: string | null;
  terms: string | null;
  points_value: number;
  is_active: boolean;
  created_at: string;
}

export interface ProductWithCounts extends Product {
  units_generated: number;
  units_claimed: number;
  units_available: number;
  units_void: number;
}

export interface Batch {
  id: string;
  product_id: string;
  quantity: number;
  label: string | null;
  created_at: string;
}

export interface OrderBatchLine {
  batch_id: string;
  product_id: string;
  product_name: string;
  quantity: number;
}

export interface OrderResult {
  label: string | null;
  total_units: number;
  batches: OrderBatchLine[];
}

export type UnitStatus = 'active' | 'claimed' | 'void';

export interface Unit {
  id: string;
  product_id: string;
  token: string;
  status: UnitStatus;
  batch_id: string | null;
  claimed_by_user_id: string | null;
  claimed_at: string | null;
  created_at: string;
}

export type LedgerType =
  | 'scan_credit'
  | 'return_reversal'
  | 'redemption_debit'
  | 'admin_credit'
  | 'admin_debit';

export interface LedgerEntry {
  id: string;
  amount: number;
  type: LedgerType;
  note: string | null;
  product_unit_id: string | null;
  redemption_id: string | null;
  created_at: string;
}

export interface LedgerPage {
  items: LedgerEntry[];
  next_cursor: string | null;
}

export interface UnitDetail extends Unit {
  product_name: string | null;
  claimed_by_name: string | null;
  claimed_by_phone: string | null;
  history: LedgerEntry[];
}

export interface ReactivateResult {
  unit: Unit;
  reversed_points: number;
  user_id: string;
}

export interface AdminUser {
  id: string;
  phone: string;
  name: string;
  is_verified: boolean;
  is_active: boolean;
  balance: number;
  total_earned: number;
  last_active_at: string | null;
  created_at: string;
}

export interface AdminUserDetail extends AdminUser {
  available: number;
}

export interface UserListPage {
  items: AdminUser[];
  next_cursor: string | null;
}

export type RedemptionStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'fulfilled'
  | 'cancelled';

export interface Redemption {
  id: string;
  points: number;
  status: RedemptionStatus;
  note: string | null;
  created_at: string;
  processed_at: string | null;
  user: { id: string; phone: string; name: string };
  reward_id: string | null;
  reward: { id: string; title: string } | null;
}

export interface Reward {
  id: string;
  title: string;
  description: string | null;
  points_cost: number;
  image_url: string | null;
  is_active: boolean;
  sort_order: number;
  created_at: string;
}

export interface RewardInput {
  title: string;
  description?: string | null;
  points_cost: number;
  image_url?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

export interface Faq {
  id: string;
  question: string;
  answer: string;
  sort_order: number;
  is_published: boolean;
  created_at: string;
}

export interface FaqInput {
  question: string;
  answer: string;
  sort_order?: number;
  is_published?: boolean;
}

export interface ContentDoc {
  key: string;
  title: string;
  body: string;
  updated_at: string;
}

export interface ContentDocInput {
  title: string;
  body: string;
}

export interface Dashboard {
  total_users: number;
  total_points_outstanding: number;
  total_scans: number;
  scans_today: number;
  scans_this_week: number;
  pending_redemptions: number;
  products_in_catalog: number;
}

export interface ScanFeedItem {
  id: string;
  user: { id: string; phone: string; name: string };
  product: { id: string; name: string };
  product_unit_id: string | null;
  points: number;
  scanned_at: string;
}

export interface ScanFeedPage {
  items: ScanFeedItem[];
  next_cursor: string | null;
}

export interface AuditItem {
  id: string;
  actor_admin_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditPage {
  items: AuditItem[];
  next_cursor: string | null;
}

export interface ScanDayPoint {
  date: string;
  scans: number;
  points: number;
}

export interface TopProduct {
  id: string;
  name: string;
  claimed: number;
}

export interface DashboardAnalytics {
  scans_by_day: ScanDayPoint[];
  redemptions_by_status: Record<string, number>;
  top_products: TopProduct[];
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}
