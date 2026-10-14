import { ChartLine, DocumentView, Money, Renew, Rule, WarningAlt } from '@carbon/icons-react';
import { Header, HeaderGlobalAction, HeaderGlobalBar, HeaderName } from '@carbon/react';
import { Link, NavLink, Outlet } from 'react-router-dom';

const navigation = [
  { to: '/', label: 'Overview', icon: ChartLine, end: true },
  { to: '/violations', label: 'Violations', icon: WarningAlt, end: false },
  { to: '/audit', label: 'Audit log', icon: DocumentView, end: false },
  { to: '/usage', label: 'Usage & ROI', icon: Money, end: false },
  { to: '/rules', label: 'Rules', icon: Rule, end: false },
];

function ProductMark() {
  return (
    <svg className="product-mark" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M10 1.5 17.5 4.5v5.2c0 4.3-3.1 7.6-7.5 8.8-4.4-1.2-7.5-4.5-7.5-8.8V4.5L10 1.5Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="m6.6 10 2.4 2.4 4.6-4.8" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Header aria-label="Governance">
        <HeaderName as={Link} to="/" prefix=""><ProductMark /><span>Governance</span></HeaderName>
        <HeaderGlobalBar>
          <HeaderGlobalAction aria-label="Refresh page" onClick={() => window.location.reload()}><Renew /></HeaderGlobalAction>
        </HeaderGlobalBar>
      </Header>
      <aside className="side-rail" aria-label="Primary navigation">
        <nav>
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink to={to} end={end} key={to} className={({ isActive }) => `side-link${isActive ? ' side-link--active' : ''}`}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-rail__status"><span className="status-dot" /><div><strong>Controls active</strong><span>Hooks reporting</span></div></div>
      </aside>
      <main className="main-content" id="main-content"><Outlet /></main>
    </div>
  );
}
