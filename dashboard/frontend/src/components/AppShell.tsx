import { Activity, Catalog, ChartLine, Policy, Renew, UserMultiple } from '@carbon/icons-react';
import { Header, HeaderGlobalAction, HeaderGlobalBar, HeaderName } from '@carbon/react';
import { Link, NavLink, Outlet } from 'react-router-dom';

const navigation = [
  { to: '/overview', label: 'Overview', icon: ChartLine },
  { to: '/activity', label: 'Activity', icon: Activity },
  { to: '/users', label: 'Users', icon: UserMultiple },
  { to: '/policies', label: 'Policies', icon: Policy },
];

export function AppShell() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <Header aria-label="Governance">
        <HeaderName as={Link} to="/overview" prefix="">Governance</HeaderName>
        <span className="header-context">IBM Bob</span>
        <HeaderGlobalBar>
          <HeaderGlobalAction aria-label="Refresh page" onClick={() => window.location.reload()}><Renew /></HeaderGlobalAction>
        </HeaderGlobalBar>
      </Header>
      <aside className="side-rail" aria-label="Primary navigation">
        <div className="side-rail__marker"><Catalog size={20} /><span>Policy operations</span></div>
        <nav>
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink to={to} key={to} className={({ isActive }) => `side-link${isActive ? ' side-link--active' : ''}`}>
              <Icon size={18} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-rail__status"><span className="status-dot" /><div><strong>Controls active</strong><span>Policy decisions reporting</span></div></div>
      </aside>
      <main className="main-content" id="main-content"><Outlet /></main>
    </div>
  );
}
