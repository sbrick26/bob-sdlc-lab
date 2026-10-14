import assert from 'node:assert/strict';
import test from 'node:test';
import { bobcoins, bucketLabel, count, median, minutes, percent, readNumber, roi, toUsd, usd, writeNumber } from '../src/format.ts';

test('Bobcoins carry two decimals and the BC unit, USD a leading $', () => {
  assert.equal(bobcoins(3.87), '3.87 BC');
  assert.equal(bobcoins(1234.5), '1,234.50 BC');
  assert.equal(usd(1.94), '$1.94');
  assert.equal(toUsd(3.87, 0.5), 1.94);
  assert.equal(usd(toUsd(3.87, 0.5)), '$1.94');
  assert.equal(toUsd(3.87, null), null);
  assert.equal(toUsd(null, 0.5), null);
});

test('missing and non-finite values never render as NaN', () => {
  for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.equal(count(value), '—');
    assert.equal(bobcoins(value), '—');
    assert.equal(usd(value), '—');
    assert.equal(minutes(value), '—');
    assert.equal(percent(value), '—');
  }
  assert.equal(count(42000), '42,000');
  assert.equal(median([]), null);
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([1, 2, 3, 4]), 2.5);
});

test('minutes read as hours past one hour', () => {
  assert.equal(minutes(45), '45 min');
  assert.equal(minutes(128), '2 h 8 min');
  assert.equal(minutes(120), '2 h');
});

test('ROI: hours saved against the baseline, Bobcoins and USD per merged PR', () => {
  const input = { merged: 3, merged_minutes_total: 390, bobcoins_merged_total: 9, ci_with_result: 4, ci_first_try_passed: 3 };
  const result = roi(input, 4, 0.5);
  assert.equal(result.hoursSaved, 5.5); // 3 x 4 h - 6.5 h
  assert.equal(result.bobcoinsPerPr, 3);
  assert.equal(result.usdPerPr, 1.5);
  assert.equal(result.firstTryRate, 75);
  const empty = roi({ merged: 0, merged_minutes_total: 0, bobcoins_merged_total: null, ci_with_result: 0, ci_first_try_passed: 0 }, 4, null);
  assert.deepEqual(empty, { hoursSaved: null, actualHours: 0, bobcoinsPerPr: null, usdPerPr: null, firstTryRate: null });
});

test('stored numbers fall back safely when storage throws or holds junk', () => {
  const memory = new Map<string, string>();
  const store = { getItem: (key: string) => memory.get(key) ?? null, setItem: (key: string, value: string) => { memory.set(key, value); } };
  assert.equal(readNumber('k', 4, store), 4);
  writeNumber('k', 6, store);
  assert.equal(readNumber('k', 4, store), 6);
  memory.set('k', 'abc');
  assert.equal(readNumber('k', 4, store), 4);
  const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
  assert.equal(readNumber('k', 4, broken), 4);
  assert.doesNotThrow(() => writeNumber('k', 5, broken));
  assert.equal(readNumber('k', null, null), null);
});

test('bucket labels for day and hour buckets', () => {
  assert.equal(bucketLabel('2026-10-13', 'day'), 'Oct 13');
  assert.match(bucketLabel('2026-10-13T14:00:00Z', 'hour'), /PM|AM/);
  assert.equal(bucketLabel('not a date', 'day'), 'not a date');
});

import { deltaText, presetRange, rangeDays, seconds } from '../src/format.ts';

test('date presets give inclusive local ranges', () => {
  const today = new Date(2026, 9, 13);
  assert.deepEqual(presetRange('today', today), { since: '2026-10-13', until: '2026-10-13' });
  assert.deepEqual(presetRange('7d', today), { since: '2026-10-07', until: '2026-10-13' });
  assert.deepEqual(presetRange('30d', today), { since: '2026-09-14', until: '2026-10-13' });
  assert.deepEqual(presetRange('month', today), { since: '2026-10-01', until: '2026-10-13' });
  assert.deepEqual(presetRange('custom', today, { since: '2026-10-01', until: '2026-10-03' }), { since: '2026-10-01', until: '2026-10-03' });
  assert.deepEqual(presetRange('custom', today, { since: '2026-10-05', until: '2026-10-03' }), { since: '2026-10-07', until: '2026-10-13' });
  assert.equal(rangeDays('2026-10-07', '2026-10-13'), 7);
});

test('deltas: tone only where direction has a meaning, nothing without prior data', () => {
  assert.deepEqual(deltaText(12.4, 7, 'up'), { text: '+12% vs prior 7 days', tone: 'good' });
  assert.deepEqual(deltaText(12.4, 7, 'down'), { text: '+12% vs prior 7 days', tone: 'bad' });
  assert.deepEqual(deltaText(-30, 1, null), { text: '−30% vs prior day', tone: 'neutral' });
  assert.equal(deltaText(null, 7, 'up'), null);
  assert.equal(seconds(4.5), '4.5 s');
  assert.equal(seconds(510), '8.5 min');
});

import { bucketLabel as label2, eventWords, freshIds } from '../src/format.ts';

test('new-row highlight only for rows that arrive by the live stream after the first load', () => {
  const before = new Set(['a', 'b']);
  assert.deepEqual([...freshIds(null, ['a', 'b'], true, false)], []);              // first load or page refresh
  assert.deepEqual([...freshIds(before, ['c', 'a', 'b'], false, true)], ['c']);    // stream refetch
  assert.deepEqual([...freshIds(before, ['c', 'a', 'b'], true, true)], []);        // filter changed: new baseline
  assert.deepEqual([...freshIds(before, ['c', 'a', 'b'], false, false)], []);      // manual refresh, not the stream
});

test('plain words for event types and bucket labels', () => {
  assert.equal(eventWords('UserPromptSubmit'), 'Prompt sent');
  assert.equal(eventWords('Stop'), 'Turn ended');
  assert.equal(eventWords('lab.ci_result'), 'CI review');
  assert.equal(eventWords('Custom'), 'Custom');
  assert.equal(label2('2026-10-06', 'week'), 'Week of Oct 6');
  assert.equal(label2('2026-10-01', 'month'), 'Oct 2026');
});

import { drillHref, filterChips, toolWords } from '../src/format.ts';

test('drill-down links and filter chips', () => {
  assert.equal(drillHref('audit', { tool: 'execute_command', outcome: 'failed', user: '' }), '#/audit?tool=execute_command&outcome=failed');
  assert.equal(drillHref('violations', {}), '#/violations');
  const chips = filterChips(new URLSearchParams('tool=execute_command&outcome=failed&decision=observed&session=abcdef1234567'));
  assert.deepEqual(chips.map((chip) => chip.label), ['Decision: Flagged', 'Session: abcdef12', 'Tool: Run command', 'Outcome: failed']);
  assert.equal(toolWords('apply_diff'), 'Edit file');
});
