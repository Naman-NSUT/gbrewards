import { useEffect } from 'react';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';

import { ErrorBoundary } from './components/ErrorBoundary';
import { Layout } from './components/Layout';
import { ClaimPage } from './pages/ClaimPage';
import { ClaimStatusPage } from './pages/ClaimStatusPage';
import { ConfirmPage } from './pages/ConfirmPage';
import { LookupPage } from './pages/LookupPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { SelfRegisterPage } from './pages/SelfRegisterPage';

const TITLES: Record<string, string> = {
  '/': 'GoodBed Warranty Support',
  '/register': 'Register your warranty · GoodBed',
  '/claim': 'Raise a warranty claim · GoodBed',
  '/claim/status': 'Track your claim · GoodBed',
};

/**
 * Title and scroll position on navigation.
 *
 * A SPA does neither by default, and both matter here: the title is what a
 * customer sees in their tab history when they come back a week later, and
 * without the scroll reset a person who scrolled to the bottom of the lookup
 * page lands halfway down the registration form.
 */
function RouteChrome() {
  const { pathname } = useLocation();

  useEffect(() => {
    // `/claims/ABCD1234` carries the reference in the path, so it is matched by
    // prefix rather than looked up whole — a title per claim reference would be
    // an entry in the map for every claim ever filed.
    const title = pathname.startsWith('/claims/')
      ? 'Track your claim · GoodBed'
      : TITLES[pathname];
    document.title = title ?? 'GoodBed Warranty Support';
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname]);

  return null;
}

export function App() {
  return (
    <BrowserRouter basename="/warranty">
      <RouteChrome />
      <Layout>
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<LookupPage />} />
            <Route path="/register" element={<SelfRegisterPage />} />
            <Route path="/claim" element={<ClaimPage />} />
            <Route path="/claim/status" element={<ClaimStatusPage />} />
            {/* The destination of the claim SMS: the backend sends
                `{public_base_url}/claims/{reference}`, so this path is not
                optional — without it every claim message lands on Not Found. */}
            <Route path="/claims/:reference" element={<ClaimStatusPage />} />
            {/* The destination of the warranty SMS. Kept short because it is
                typed by hand off a phone screen more often than anyone expects. */}
            <Route path="/w/:warrantyId" element={<ConfirmPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </Layout>
    </BrowserRouter>
  );
}
