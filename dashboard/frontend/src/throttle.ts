// Run `fn` at most once per `wait` ms: the first call runs at once, calls inside
// the window collapse into one trailing run. Timers are injectable for tests.

export interface Timers {
  now: () => number;
  setTimeout: (fn: () => void, ms: number) => unknown;
  clearTimeout: (handle: unknown) => void;
}

const realTimers: Timers = {
  now: () => Date.now(),
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (handle) => globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>),
};

export function throttle(fn: () => void, wait: number, timers: Timers = realTimers) {
  let last = -Infinity;
  let pending: unknown = null;
  const run = () => { pending = null; last = timers.now(); fn(); };
  const call = () => {
    const elapsed = timers.now() - last;
    if (elapsed >= wait && pending == null) { run(); return; }
    if (pending == null) pending = timers.setTimeout(run, Math.max(0, wait - elapsed));
  };
  call.cancel = () => { if (pending != null) timers.clearTimeout(pending); pending = null; };
  return call;
}
