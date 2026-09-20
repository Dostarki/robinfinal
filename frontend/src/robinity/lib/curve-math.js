export const CURVE_SUPPLY = 200_000_000;
export const CURVE_TARGET = 100_000;
export const PRICE_START = 0.0001;
export const PRICE_END = 0.0009;
export const CURVE_K = (PRICE_END - PRICE_START) / CURVE_SUPPLY;

export function marginalPrice(tokensSold) {
  const sold = Math.max(0, Math.min(CURVE_SUPPLY, Number(tokensSold) || 0));
  return PRICE_START + CURVE_K * sold;
}

export function revenueAt(tokensSold) {
  const sold = Math.max(0, Math.min(CURVE_SUPPLY, Number(tokensSold) || 0));
  return PRICE_START * sold + CURVE_K * sold * sold / 2;
}

export function soldAtRevenue(raisedUsd) {
  const raised = Math.max(0, Math.min(CURVE_TARGET, Number(raisedUsd) || 0));
  return (Math.sqrt(PRICE_START ** 2 + 2 * CURVE_K * raised) - PRICE_START) / CURVE_K;
}

export function quoteCurve(raisedBeforeUsd, requestedUsd) {
  const raiseBefore = Math.max(0, Math.min(CURVE_TARGET, Number(raisedBeforeUsd) || 0));
  const requested = Math.max(0, Number(requestedUsd) || 0);
  const priorSold = soldAtRevenue(raiseBefore);
  const acceptedUsd = Math.min(requested, CURVE_TARGET - raiseBefore);
  const finalSold = soldAtRevenue(raiseBefore + acceptedUsd);
  const tokens = Math.max(0, finalSold - priorSold);
  return {
    priorSold,
    finalSold,
    acceptedUsd,
    tokens,
    averagePrice: tokens ? acceptedUsd / tokens : 0,
    nextPrice: marginalPrice(finalSold),
    raisedAfterUsd: raiseBefore + acceptedUsd,
    remainingTokens: CURVE_SUPPLY - finalSold
  };
}
