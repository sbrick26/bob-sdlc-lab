import { Pagination, Search, Table, TableBody, TableCell, TableContainer, TableHead, TableHeader, TableRow } from '@carbon/react';
import { useMemo, useState, type ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  numeric?: boolean;
  render: (row: T) => ReactNode;
  /** Value used for sorting and searching; columns without it are not sortable. */
  sort?: (row: T) => number | string | null | undefined;
  /** Fixed width, e.g. "7rem". Numeric columns default to 7.5rem; others share the rest. */
  width?: string;
  /** Header hover text explaining the column. */
  title?: string;
}

/**
 * Carbon table with search, sortable columns and 25-row pages.
 * Numeric columns align right with tabular figures.
 */
export function NumberTable<T>({ columns, rows, rowKey, label, rowClass, pageSize: initialSize = 25, searchable = rows.length > 10, minWidth, rowHref }: {
  columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string; label: string; rowClass?: (row: T) => string | undefined;
  pageSize?: number; searchable?: boolean; minWidth?: string; rowHref?: (row: T) => string | undefined;
}) {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<{ key: string; dir: 'ASC' | 'DESC' } | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialSize);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    let result = needle
      ? rows.filter((row) => columns.some((column) => String(column.sort?.(row) ?? '').toLowerCase().includes(needle)))
      : rows;
    const column = sort && columns.find((item) => item.key === sort.key);
    if (column?.sort && sort) {
      const value = column.sort;
      result = [...result].sort((a, b) => {
        const left = value(a); const right = value(b);
        if (left == null && right == null) return 0;
        if (left == null) return 1;
        if (right == null) return -1;
        const order = typeof left === 'number' && typeof right === 'number' ? left - right : String(left).localeCompare(String(right));
        return sort.dir === 'ASC' ? order : -order;
      });
    }
    return result;
  }, [rows, columns, query, sort]);
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize);
  const toggle = (key: string) => setSort((current) => (current?.key === key ? { key, dir: current.dir === 'DESC' ? 'ASC' : 'DESC' } : { key, dir: 'DESC' }));
  return (
    <div className="number-table-wrap">
      {searchable && <Search size="sm" labelText={`Search ${label}`} placeholder={`Search ${label.toLowerCase()}`} value={query} onChange={(event) => { setQuery(event.currentTarget.value); setPage(1); }} className="table-search" />}
      <TableContainer className="event-table-wrap number-table">
        <Table size="md" aria-label={label} className={`fixed-table${minWidth ? ' fixed-table--wide' : ''}`}>
          <colgroup>{columns.map((column) => <col key={column.key} style={{ width: column.width ?? (column.numeric ? '7.5rem' : undefined) }} />)}</colgroup>
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableHeader key={column.key} className={column.numeric ? 'num' : undefined} isSortable={!!column.sort}
                  sortDirection={sort?.key === column.key ? sort.dir : 'NONE'} isSortHeader={sort?.key === column.key}
                  onClick={column.sort ? () => toggle(column.key) : undefined}>
                  {column.title ? <span title={column.title}>{column.header}</span> : column.header}
                </TableHeader>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {visible.map((row) => (
              <TableRow key={rowKey(row)} className={[rowClass?.(row), rowHref?.(row) ? 'row--link' : ''].filter(Boolean).join(' ') || undefined}
                onClick={rowHref?.(row) ? (event) => { if ((event.target as HTMLElement).closest('a,button')) return; window.location.hash = rowHref(row)!.replace(/^#/, ''); } : undefined}>{columns.map((column) => <TableCell key={column.key} className={column.numeric ? 'num' : undefined}>{column.render(row)}</TableCell>)}</TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {filtered.length > pageSize && (
        <Pagination page={page} pageSize={pageSize} pageSizes={[25, 50, 100]} totalItems={filtered.length} onChange={({ page: next, pageSize: size }) => { setPage(next); setPageSize(size); }} />
      )}
    </div>
  );
}
