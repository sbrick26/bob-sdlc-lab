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
