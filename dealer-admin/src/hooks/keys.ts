/**
 * Every query key in one file.
 *
 * Cache correctness here is not cosmetic: approving a backdate moves points,
 * changes a dealer's compliance rate and writes an audit row, and an admin who
 * still sees the old numbers will approve it a second time. Listing the keys
 * together is what makes "what else did this change?" answerable at the call
 * site instead of guessed at.
 */
export const qk = {
  me: ['admin', 'me'] as const,

  dashboard: ['dashboard'] as const,
  dashboardStats: () => ['dashboard', 'stats'] as const,
  dashboardAnalytics: (days: number) => ['dashboard', 'analytics', days] as const,

  compliance: ['compliance'] as const,
  complianceList: (params: unknown) => ['compliance', 'list', params] as const,
  complianceDetail: (dealerId: string | null, params: unknown) =>
    ['compliance', 'detail', dealerId, params] as const,

  approvals: ['approvals'] as const,
  approvalsList: (params: unknown) => ['approvals', 'list', params] as const,
  approvalCounts: () => ['approvals', 'counts'] as const,

  warranties: ['warranties'] as const,
  warrantyList: (params: unknown) => ['warranties', 'list', params] as const,
  warrantyDetail: (id: string | null) => ['warranties', 'detail', id] as const,

  lookup: ['lookup'] as const,
  lookupSerial: (serial: string) => ['lookup', serial] as const,

  claims: ['claims'] as const,
  claimList: (params: unknown) => ['claims', 'list', params] as const,
  claimDetail: (id: string | null) => ['claims', 'detail', id] as const,

  dealers: ['dealers'] as const,
  dealerList: (params: unknown) => ['dealers', 'list', params] as const,
  dealerDetail: (id: string | null) => ['dealers', 'detail', id] as const,
  dealerStaff: (id: string | null) => ['dealers', 'staff', id] as const,
  dealerLedger: (id: string | null, params: unknown) => ['dealers', 'ledger', id, params] as const,
  dealerPoints: (id: string | null) => ['dealers', 'points', id] as const,

  rewards: ['rewards'] as const,
  rewardList: (params: unknown) => ['rewards', 'list', params] as const,

  redemptions: ['redemptions'] as const,
  redemptionList: (params: unknown) => ['redemptions', 'list', params] as const,

  sms: ['sms'] as const,
  smsList: (params: unknown) => ['sms', 'list', params] as const,
  smsTemplates: () => ['sms', 'templates'] as const,

  points: ['points'] as const,
  pointRate: () => ['points', 'rate'] as const,
  pointRates: (params: unknown) => ['points', 'rates', params] as const,

  audit: ['audit'] as const,
  auditList: (params: unknown) => ['audit', 'list', params] as const,
  auditFilters: () => ['audit', 'filters'] as const,
};
