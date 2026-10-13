import { Button, InlineNotification, Loading } from '@carbon/react';

export function PageLoading() {
  return <div className="page-state"><Loading withOverlay={false} description="Loading governance data" /></div>;
}

export function PageError({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div className="page-state page-state--wide">
      <InlineNotification kind="error" title="Data could not be loaded" subtitle={error.message} lowContrast hideCloseButton />
      <Button kind="tertiary" size="sm" onClick={retry}>Try again</Button>
    </div>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><h3>{title}</h3><p>{detail}</p></div>;
}
