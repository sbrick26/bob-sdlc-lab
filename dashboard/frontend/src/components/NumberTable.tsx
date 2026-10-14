import { Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from '@carbon/react';
import type { ReactNode } from 'react';

export interface Column<T> { key: string; header: string; numeric?: boolean; render: (row: T) => ReactNode }

/** A plain Carbon table; numeric columns align right with tabular figures. */
export function NumberTable<T>({ columns, rows, rowKey, label, rowClass }: { columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string; label: string; rowClass?: (row: T) => string | undefined }) {
  return (
    <TableContainer className="event-table-wrap number-table">
      <Table size="md" aria-label={label}>
        <TableHead><TableRow>{columns.map((column) => <TableHeader key={column.key} className={column.numeric ? 'num' : undefined}>{column.header}</TableHeader>)}</TableRow></TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={rowKey(row)} className={rowClass?.(row)}>{columns.map((column) => <TableCell key={column.key} className={column.numeric ? 'num' : undefined}>{column.render(row)}</TableCell>)}</TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
