export function isIconAvatar(avatar: null | string | undefined): boolean {
  return Boolean(avatar && String(avatar).includes(':'));
}

export function getInitialLetter(value: null | string | undefined): string {
  const text = String(value || '').trim();
  return text ? text.charAt(0).toUpperCase() : '?';
}

export function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => asString(item))
    .filter(
      (item, index, list) => Boolean(item) && list.indexOf(item) === index,
    );
}

export function asRecord(
  value: null | Record<string, unknown> | unknown,
): null | Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function asRecordArray<T extends Record<string, unknown>>(
  value: unknown,
): T[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is T =>
      Boolean(item) && typeof item === 'object' && !Array.isArray(item),
  );
}

export function hasEntries(
  value: null | Record<string, unknown> | undefined,
): boolean {
  return Boolean(value && Object.keys(value).length > 0);
}

export function formatCost(cost?: null | number, digits = 4): string {
  return `$${Number(cost || 0).toFixed(digits)}`;
}

export function formatTokens(tokens?: null | number): string {
  return Number(tokens || 0).toLocaleString();
}

export function formatTagValue(value: null | string | undefined): string {
  return asString(value) || '-';
}

export function truncateText(text: unknown, maxLen: number): string {
  const s = typeof text === 'string' ? text : '';
  return s.length > maxLen ? `${s.slice(0, maxLen)}...` : s;
}

export function roleColor(role: string): string {
  switch (role) {
    case 'assistant': {
      return 'success';
    }
    case 'system': {
      return 'orange';
    }
    case 'tool': {
      return 'purple';
    }
    default: {
      return 'blue';
    }
  }
}

export function conversationStatusColor(status?: null | string): string {
  switch (status) {
    case 'active': {
      return 'success';
    }
    case 'closed': {
      return 'error';
    }
    default: {
      return 'default';
    }
  }
}

export function traceStatusColor(status?: null | string): string {
  return status === 'success' ? 'success' : 'error';
}
