import { Theme } from '@carbon/react';
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { PageLoading } from './components/States';
import { FiltersProvider, LiveProvider } from './context';
import { useDarkMode } from './theme';

const OverviewPage = lazy(() => import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })));
const UsagePage = lazy(() => import('./pages/UsagePage').then((module) => ({ default: module.UsagePage })));
const DeliveryPage = lazy(() => import('./pages/DeliveryPage').then((module) => ({ default: module.DeliveryPage })));
const PerformancePage = lazy(() => import('./pages/PerformancePage').then((module) => ({ default: module.PerformancePage })));
const ViolationsPage = lazy(() => import('./pages/ViolationsPage').then((module) => ({ default: module.ViolationsPage })));
const AuditLogPage = lazy(() => import('./pages/AuditLogPage').then((module) => ({ default: module.AuditLogPage })));

export function App() {
  const dark = useDarkMode();
  return (
    <Theme theme={dark ? 'g100' : 'g10'} className={`theme-root${dark ? ' theme-root--dark' : ''}`}>
      <FiltersProvider>
        <LiveProvider>
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<OverviewPage />} />
                <Route path="usage" element={<UsagePage />} />
                <Route path="cost" element={<Navigate to="/usage" replace />} />
                <Route path="delivery" element={<DeliveryPage />} />
                <Route path="performance" element={<PerformancePage />} />
                <Route path="violations" element={<ViolationsPage />} />
                <Route path="audit" element={<AuditLogPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </LiveProvider>
      </FiltersProvider>
    </Theme>
  );
}
