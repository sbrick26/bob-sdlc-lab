import { DataTable, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from '@carbon/react';
import type { GovernanceEvent } from '../types';
import { DecisionTag } from './DecisionTag';

const headers = [
  { key: 'occurred_at', header: 'Time' },
  { key: 'user_name', header: 'User' },
  { key: 'lab_ticket', header: 'Ticket' },
  { key: 'hook_event', header: 'Event type' },
  { key: 'tool_name', header: 'Tool' },
  { key: 'rule_name', header: 'Rule' },
  { key: 'decision', header: 'Decision' },
];

export function EventTable({ events, onSelect, compact = false }: { events: GovernanceEvent[]; onSelect: (event: GovernanceEvent) => void; compact?: boolean }) {
  const rows = events.map((event) => ({
    ...event,
    id: event.event_id,
    occurred_at: new Date(event.occurred_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }),
    rule_name: event.rule_name || '—',
    tool_name: event.tool_name || '—',
    lab_ticket: event.lab_ticket || '—',
  }));
  const visibleHeaders = compact ? headers.slice(0, 5) : headers;
  return (
    <DataTable rows={rows} headers={visibleHeaders} isSortable>
      {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => (
        <TableContainer className="event-table-wrap">
          <Table {...getTableProps()} size={compact ? 'sm' : 'md'} useZebraStyles={false}>
            <TableHead><TableRow>{tableHeaders.map((header) => <TableHeader {...getHeaderProps({ header })} key={header.key}>{header.header}</TableHeader>)}</TableRow></TableHead>
            <TableBody>
              {tableRows.map((row) => {
                const event = events.find((item) => item.event_id === row.id)!;
                return (
                  <TableRow {...getRowProps({ row })} key={row.id} onClick={() => onSelect(event)} className="event-row">
                    {row.cells.map((cell) => <TableCell key={cell.id}>{cell.info.header === 'decision' ? <DecisionTag decision={event.decision} /> : String(cell.value)}</TableCell>)}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </DataTable>
  );
}
