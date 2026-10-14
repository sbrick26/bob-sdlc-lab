import { ChartLine, Dashboard, DeliveryParcel, DocumentView, Money, Renew, Settings, WarningAlt } from '@carbon/icons-react';
import { useLive } from '../context';
import { Header, HeaderGlobalAction, HeaderGlobalBar, HeaderName } from '@carbon/react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import ibmLogo from '../assets/ibm-logo.svg';
import bobMark from '../assets/bob.webp';

const navigation = [
  { to: '/', label: 'Overview', icon: ChartLine, end: true },
  { to: '/usage', label: 'Usage', icon: Money, end: false },
  { to: '/delivery', label: 'Delivery', icon: DeliveryParcel, end: false },
  { to: '/performance', label: 'Performance', icon: Dashboard, end: false },
  { to: '/violations', label: 'Violations', icon: WarningAlt, end: false },
  { to: '/audit', label: 'Audit log', icon: DocumentView, end: false },
];

function LiveIndicator() {
  const { status, toggle } = useLive();
  const label = status === 'live' ? 'Live' : status === 'paused' ? 'Paused' : 'Reconnecting';
  return (
    <button type="button" className={`live-indicator live-indicator--${status}`} onClick={toggle} title={status === 'paused' ? 'Resume live updates' : 'Pause live updates'}>
      <span className="live-indicator__dot" aria-hidden="true" />{label}
    </button>
  );
}

/** IBM 8-bar logo, from src/assets/ibm-logo.svg, painted in the header's logo color through a CSS mask. */
function IbmLogo() {
  return <span className="ibm-logo" role="img" aria-label="IBM" style={{ WebkitMaskImage: `url("${ibmLogo}")`, maskImage: `url("${ibmLogo}")` }} />;
}

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Header aria-label="Governance">
        <HeaderName as={Link} to="/" prefix="" aria-label="Bob Governance"><IbmLogo /><span className="header-divider" aria-hidden="true" /><img className="bob-mark" src={bobMark} alt="Bob" height={32} /></HeaderName>
        <HeaderGlobalBar>
          <LiveIndicator />
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
        <NavLink to="/settings" className={({ isActive }) => `side-link side-link--bottom${isActive ? ' side-link--active' : ''}`}><Settings size={18} /><span>Settings</span></NavLink>
      </aside>
      <main className="main-content" id="main-content"><Outlet /></main>
    </div>
  );
}
