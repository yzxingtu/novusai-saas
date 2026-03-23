function pad(value: number): string {
  return String(value).padStart(2, '0');
}

function toValidDate(value: null | string | undefined): Date | null {
  if (!value) {
    return null;
  }

  const normalized = new Date(value);
  return Number.isNaN(normalized.getTime()) ? null : normalized;
}

export function formatDateTime(value: null | string | undefined): string {
  const date = toValidDate(value);
  if (!date) {
    return '--';
  }

  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join('-')
    + ` ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function formatCompactNumber(value: null | number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return new Intl.NumberFormat('en-US').format(value);
}

export function formatCurrency(value: null | number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }
  return `¥${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
  }).format(value)}`;
}

export function formatDurationMs(value: null | number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }

  if (value < 1000) {
    return `${Math.round(value)}ms`;
  }

  if (value < 60_000) {
    return `${(value / 1000).toFixed(1)}s`;
  }

  if (value < 3_600_000) {
    return `${(value / 60_000).toFixed(1)}m`;
  }

  return `${(value / 3_600_000).toFixed(1)}h`;
}

export function formatPercent(value: null | number | undefined): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }

  const normalized = value > 1 ? value : value * 100;
  return `${normalized.toFixed(normalized >= 10 ? 0 : 1)}%`;
}

export function formatText(value: null | number | string | undefined): string {
  if (value === undefined || value === null || value === '') {
    return '--';
  }
  return String(value);
}
