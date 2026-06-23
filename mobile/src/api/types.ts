export interface UserOut {
  id: string;
  phone: string;
  name: string;
  is_verified: boolean;
  last_active_at: string | null;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user?: UserOut | null;
}

export interface Me {
  id: string;
  phone: string;
  name: string;
  is_verified: boolean;
  balance: number;
  available: number;
  last_active_at: string | null;
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
}

export interface ScanClaimResult {
  product: { id: string; name: string; points_value: number };
  points_awarded: number;
  balance: number;
  available: number;
  claimed_at: string;
  idempotent: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}
