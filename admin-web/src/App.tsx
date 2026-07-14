import { Spin } from 'antd';
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from './auth/ProtectedRoute';
import { AppLayout } from './layout/AppLayout';

const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })));
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })),
);
const ProductsPage = lazy(() =>
  import('./pages/ProductsPage').then((m) => ({ default: m.ProductsPage })),
);
const RewardsPage = lazy(() =>
  import('./pages/RewardsPage').then((m) => ({ default: m.RewardsPage })),
);
const FaqsPage = lazy(() => import('./pages/FaqsPage').then((m) => ({ default: m.FaqsPage })));
const ContentPage = lazy(() =>
  import('./pages/ContentPage').then((m) => ({ default: m.ContentPage })),
);
const UsersPage = lazy(() => import('./pages/UsersPage').then((m) => ({ default: m.UsersPage })));
const RedemptionsPage = lazy(() =>
  import('./pages/RedemptionsPage').then((m) => ({ default: m.RedemptionsPage })),
);
const ReturnsPage = lazy(() =>
  import('./pages/ReturnsPage').then((m) => ({ default: m.ReturnsPage })),
);
const UnitLookupPage = lazy(() =>
  import('./pages/UnitLookupPage').then((m) => ({ default: m.UnitLookupPage })),
);
const ScansPage = lazy(() => import('./pages/ScansPage').then((m) => ({ default: m.ScansPage })));
const AuditPage = lazy(() => import('./pages/AuditPage').then((m) => ({ default: m.AuditPage })));
const AccountPage = lazy(() =>
  import('./pages/AccountPage').then((m) => ({ default: m.AccountPage })),
);

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
          <Route path="products" element={<ProductsPage />} />
          <Route path="rewards" element={<RewardsPage />} />
          <Route path="faqs" element={<FaqsPage />} />
          <Route path="content" element={<ContentPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="redemptions" element={<RedemptionsPage />} />
          <Route path="returns" element={<ReturnsPage />} />
          <Route path="units" element={<UnitLookupPage />} />
          <Route path="scans" element={<ScansPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="account" element={<AccountPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
