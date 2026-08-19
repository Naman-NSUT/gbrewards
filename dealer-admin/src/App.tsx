import { Spin } from 'antd';
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from './auth/ProtectedRoute';
import { AppLayout } from './layout/AppLayout';

const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const CompliancePage = lazy(() =>
  import('./pages/CompliancePage').then((m) => ({ default: m.CompliancePage })),
);
const ApprovalsPage = lazy(() =>
  import('./pages/ApprovalsPage').then((m) => ({ default: m.ApprovalsPage })),
);
const WarrantiesPage = lazy(() =>
  import('./pages/WarrantiesPage').then((m) => ({ default: m.WarrantiesPage })),
);
const SerialLookupPage = lazy(() =>
  import('./pages/SerialLookupPage').then((m) => ({ default: m.SerialLookupPage })),
);
const ClaimsPage = lazy(() =>
  import('./pages/ClaimsPage').then((m) => ({ default: m.ClaimsPage })),
);
const AllocationsPage = lazy(() =>
  import('./pages/AllocationsPage').then((m) => ({ default: m.AllocationsPage })),
);
const DealersPage = lazy(() =>
  import('./pages/DealersPage').then((m) => ({ default: m.DealersPage })),
);
const RewardsPage = lazy(() =>
  import('./pages/RewardsPage').then((m) => ({ default: m.RewardsPage })),
);
const RedemptionsPage = lazy(() =>
  import('./pages/RedemptionsPage').then((m) => ({ default: m.RedemptionsPage })),
);
const SmsLogPage = lazy(() =>
  import('./pages/SmsLogPage').then((m) => ({ default: m.SmsLogPage })),
);
const PointsPage = lazy(() =>
  import('./pages/PointsPage').then((m) => ({ default: m.PointsPage })),
);
const AuditPage = lazy(() => import('./pages/AuditPage').then((m) => ({ default: m.AuditPage })));

function Fallback() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '60vh' }}>
      <Spin size="large" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Fallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="compliance" element={<CompliancePage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="warranties" element={<WarrantiesPage />} />
          <Route path="lookup" element={<SerialLookupPage />} />
          <Route path="claims" element={<ClaimsPage />} />
          <Route path="allocations" element={<AllocationsPage />} />
          <Route path="dealers" element={<DealersPage />} />
          <Route path="rewards" element={<RewardsPage />} />
          <Route path="redemptions" element={<RedemptionsPage />} />
          <Route path="sms" element={<SmsLogPage />} />
          <Route path="points" element={<PointsPage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
