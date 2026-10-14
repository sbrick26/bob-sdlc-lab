import { Theme } from '@carbon/react';
import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { PageLoading } from './components/States';
import { useDarkMode } from './theme';

const OverviewPage = lazy(() => import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })));
const ViolationsPage = lazy(() => import('./pages/ViolationsPage').then((module) => ({ default: module.ViolationsPage })));
const AuditLogPage = lazy(() => import('./pages/AuditLogPage').then((module) => ({ default: module.AuditLogPage })));
const UsagePage = lazy(() => import('./pages/UsagePage').then((module) => ({ default: module.UsagePage })));
const RulesPage = lazy(() => import('./pages/RulesPage').then((module) => ({ default: module.RulesPage })));

export function App() {
  const dark = useDarkMode();
  return (
    <Theme theme={dark ? 'g100' : 'g10'} className={`theme-root${dark ? ' theme-root--dark' : ''}`}>
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="violations" element={<ViolationsPage />} />
            <Route path="audit" element={<AuditLogPage />} />
            <Route path="usage" element={<UsagePage />} />
            <Route path="rules" element={<RulesPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </Theme>
  );
}
