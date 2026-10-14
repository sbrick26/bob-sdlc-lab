import { Dropdown, TextInput } from '@carbon/react';
import { api } from '../api';
import { useFilters } from '../context';
import { PRESETS, type Preset } from '../format';
import { useApi } from '../hooks';

/** Date range and team: every tile, chart and table on every page follows these. */
export function GlobalControls() {
  const { filters, setPreset, setCustom, setTeam } = useFilters();
  const facets = useApi(api.facets, []);
  const teams = ['', ...(facets.data?.teams ?? []).filter((team) => team !== 'unassigned')];
  return (
    <div className="global-controls">
      <Dropdown
        id="global-range" size="sm" titleText="Date range" label="Date range" items={PRESETS}
        selectedItem={PRESETS.find((item) => item.id === filters.preset)}
        itemToString={(item) => item?.label ?? ''}
        onChange={({ selectedItem }) => selectedItem && setPreset(selectedItem.id as Preset)}
      />
      {filters.preset === 'custom' && (
        <>
          <TextInput id="global-since" size="sm" type="date" labelText="From" value={filters.since} onChange={(event) => setCustom(event.currentTarget.value, filters.until)} />
          <TextInput id="global-until" size="sm" type="date" labelText="To" value={filters.until} onChange={(event) => setCustom(filters.since, event.currentTarget.value)} />
        </>
      )}
      <Dropdown
        id="global-team" size="sm" titleText="Team" label="All teams" items={teams}
        selectedItem={filters.team} itemToString={(item) => (item ? item : 'All teams')}
        onChange={({ selectedItem }) => setTeam(selectedItem ?? '')}
      />
    </div>
  );
}
