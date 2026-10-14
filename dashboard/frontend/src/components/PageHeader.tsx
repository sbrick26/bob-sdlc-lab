import type { ReactNode } from 'react';
import { GlobalControls } from './GlobalControls';

export function PageHeader({ title, actions, controls = true }: { title: string; actions?: ReactNode; controls?: boolean }) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      <div className="page-actions">{controls && <GlobalControls />}{actions}</div>
    </header>
  );
}
