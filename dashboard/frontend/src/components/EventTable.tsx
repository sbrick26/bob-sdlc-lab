import { DataTable, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from '@carbon/react';
import { eventWords, shortTime } from '../format';
import type { GovernanceEvent } from '../types';
import { DecisionTag } from './DecisionTag';

const headers = [
  { key: 'occurred_at', header: 'Time' },
  { key: 'user_name', header: 'User' },
  { key: 'team', header: 'Team' },
  { key: 'lab_ticket', header: 'Ticket' },
  { key: 'hook_event', header: 'Event type' },
  { key: 'tool_name', header: 'Tool' },
  { key: 'rule_name', header: 'Rule' },
  { key: 'decision', header: 'Decision' },
];

export function EventTable({ events, onSelect, fresh }: { events: GovernanceEvent[]; onSelect: (eventId: string) => void; fresh?: Set<string> }) {
  const rows = events.map((event) => ({
    id: event.event_id,
    occurred_at: shortTime(event.occurred_at),
    user_name: event.lab_role === 'ci-reviewer' || event.user_name === 'ci-reviewer' ? 'Automated review (CI)' : event.user_name,
    team: event.team || '—',
    lab_ticket: event.lab_ticket || '—',
    hook_event: eventWords(event.hook_event),
    tool_name: event.tool_name || '—',
    rule_name: event.rule_name || '—',
    decision: event.decision,
  }));
  return (
    <DataTable rows={rows} headers={headers}>
      {({ rows: tableRows, headers: tableHeaders, getHeaderProps, getRowProps, getTableProps }) => (
        <TableContainer className="event-table-wrap">
          <Table {...getTableProps()} size="md">
            <TableHead><TableRow>{tableHeaders.map((header) => <TableHeader {...getHeaderProps({ header })} key={header.key}>{header.header}</TableHeader>)}</TableRow></TableHead>
            <TableBody>
              {tableRows.map((row) => (
                <TableRow {...getRowProps({ row })} key={row.id} onClick={() => onSelect(row.id)} tabIndex={0} onKeyDown={(event) => event.key === 'Enter' && onSelect(row.id)} className={`event-row${fresh?.has(row.id) ? ' row--new' : ''}`}>
                  {row.cells.map((cell) => <TableCell key={cell.id}>{cell.info.header === 'decision' ? <DecisionTag decision={cell.value} /> : String(cell.value)}</TableCell>)}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </DataTable>
  );
}
