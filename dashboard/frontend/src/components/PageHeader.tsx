import type { ReactNode } from 'react';
import { GlobalControls } from './GlobalControls';

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      <div className="page-actions"><GlobalControls />{actions}</div>
    </header>
  );
}
