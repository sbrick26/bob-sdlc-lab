import assert from 'node:assert/strict';
import test from 'node:test';
import { throttle, type Timers } from '../src/throttle.ts';

function fakeTimers() {
  let now = 0;
  const queue: Array<{ at: number; fn: () => void; id: number }> = [];
  let next = 1;
  const timers: Timers = {
    now: () => now,
    setTimeout: (fn, ms) => { const id = next++; queue.push({ at: now + ms, fn, id }); return id; },
    clearTimeout: (handle) => { const index = queue.findIndex((item) => item.id === handle); if (index >= 0) queue.splice(index, 1); },
  };
  const advance = (ms: number) => {
    now += ms;
    queue.sort((a, b) => a.at - b.at);
    while (queue.length && queue[0].at <= now) queue.shift()!.fn();
  };
  return { timers, advance };
}

test('live refetch runs at most once every 3 s, with one trailing run', () => {
  const { timers, advance } = fakeTimers();
  let runs = 0;
  const bump = throttle(() => { runs += 1; }, 3000, timers);
  bump();                   // first event: refetch at once
  assert.equal(runs, 1);
  for (let i = 0; i < 20; i += 1) { advance(100); bump(); } // a burst of 20 events in 2 s
  assert.equal(runs, 1);
  advance(1000);            // the window closes: one trailing refetch
  assert.equal(runs, 2);
  advance(10_000);
  assert.equal(runs, 2);    // nothing pending
  bump();
  assert.equal(runs, 3);
  bump.cancel();
});
