import { useState } from 'react';
import { api } from '../api';
import type { EventView, GovernanceEvent } from '../types';
import { EventDetail } from './EventDetail';

/** Open the detail drawer for an event id; returns the opener and the drawer element. */
export function useEventDrawer() {
  const [open, setOpen] = useState(false);
  const [event, setEvent] = useState<GovernanceEvent | null>(null);
  const [view, setView] = useState<EventView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const show = async (eventId: string) => {
    setOpen(true); setLoading(true); setError(null); setEvent(null); setView(null);
    try {
      const result = await api.event(eventId);
      setEvent(result.event); setView(result.view);
    } catch (value) {
      setError(value instanceof Error ? value.message : 'The event could not be loaded.');
    } finally {
      setLoading(false);
    }
  };
  const drawer = open ? <EventDetail event={event} view={view} loading={loading} error={error} onClose={() => setOpen(false)} /> : null;
  return { show, drawer };
}
