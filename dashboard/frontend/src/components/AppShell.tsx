import { ChartLine, DocumentView, Money, Renew, Rule, WarningAlt } from '@carbon/icons-react';
import { Header, HeaderGlobalAction, HeaderGlobalBar, HeaderName } from '@carbon/react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import ibmLogo from '../assets/ibm-logo.svg';

const navigation = [
  { to: '/', label: 'Overview', icon: ChartLine, end: true },
  { to: '/violations', label: 'Violations', icon: WarningAlt, end: false },
  { to: '/audit', label: 'Audit log', icon: DocumentView, end: false },
  { to: '/usage', label: 'Usage & ROI', icon: Money, end: false },
  { to: '/rules', label: 'Rules', icon: Rule, end: false },
];

/** IBM 8-bar logo, from src/assets/ibm-logo.svg, painted in the header's logo color through a CSS mask. */
function IbmLogo() {
  return <span className="ibm-logo" role="img" aria-label="IBM" style={{ WebkitMaskImage: `url("${ibmLogo}")`, maskImage: `url("${ibmLogo}")` }} />;
}

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Header aria-label="Governance">
        <HeaderName as={Link} to="/" prefix=""><IbmLogo /><span className="header-title">Governance</span></HeaderName>
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
