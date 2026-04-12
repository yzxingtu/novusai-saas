export function formatCost(cost?: null | number, digits = 4): string {
  return `$${Number(cost || 0).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function formatNumber(value?: null | number): string {
  return Number(value || 0).toLocaleString();
}

export function formatPercent(value?: null | number): string {
  return `${Number(value || 0)
    .toFixed(1)
    .replace(/\.0$/, '')}%`;
}

export function formatShare(value: number, total: number): string {
  if (!total) {
    return '0%';
  }
  return formatPercent((value / total) * 100);
}

export function progressWidth(
  value: number,
  total: number,
  minimum = 0,
): string {
  if (!total) {
    return '0%';
  }
  const width = (value / total) * 100;
  return `${Math.max(width, minimum)}%`;
}

export function maxCallCount(items: { call_count: number }[]): number {
  return Math.max(...items.map((item) => item.call_count), 0);
}
