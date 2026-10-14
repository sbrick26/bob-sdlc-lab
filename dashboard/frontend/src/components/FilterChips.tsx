import { Tag } from '@carbon/react';
import { useSearchParams } from 'react-router-dom';
import { filterChips } from '../format';

/** Active drill-down filters from the URL as removable chips. */
export function FilterChips() {
  const [params, setParams] = useSearchParams();
  const chips = filterChips(params);
  if (!chips.length) return null;
  const remove = (key: string) => { const next = new URLSearchParams(params); next.delete(key); setParams(next, { replace: true }); };
  return (
    <div className="filter-chips" aria-label="Active filters">
      {chips.map((chip) => <Tag key={chip.key} type="blue" size="md" filter onClose={() => remove(chip.key)} title={`Remove ${chip.label}`}>{chip.label}</Tag>)}
      {chips.length > 1 && <button type="button" className="link-button" onClick={() => setParams(new URLSearchParams(), { replace: true })}>Clear all</button>}
    </div>
  );
}
