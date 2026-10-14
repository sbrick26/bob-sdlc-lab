import { Locked } from '@carbon/icons-react';
import { PageHeader } from '../components/PageHeader';

export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" controls={false} />
      <section className="panel settings-panel settings-panel--restricted">
        <Locked size={32} aria-hidden="true" />
        <h2>Restricted access</h2>
        <p>Contact your administrator for details.</p>
      </section>
    </>
  );
}
