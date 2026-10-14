import { toUsd, usd } from '../format';

/** USD for a Bobcoin figure, or "set rate" when no rate is known. */
export function usdText(coins: number | null | undefined, rate: number | null): string {
  if (coins == null) return '—';
  return rate == null ? 'set rate' : usd(toUsd(coins, rate));
}

export function rateBasis(rate: number | null, basis: string | null | undefined, fromBrowser: boolean): string {
  if (rate == null) return 'No USD rate. Set USD per Bobcoin on Usage & ROI.';
  const source = fromBrowser ? 'rate set in this browser' : basis || 'BOBCOIN_USD_RATE setting';
  return `USD at ${usd(rate)} per Bobcoin, ${source}`;
}

export function RateNote({ rate, basis, fromBrowser }: { rate: number | null; basis: string | null | undefined; fromBrowser: boolean }) {
  return <p className="rate-note">{rateBasis(rate, basis, fromBrowser)}</p>;
}
