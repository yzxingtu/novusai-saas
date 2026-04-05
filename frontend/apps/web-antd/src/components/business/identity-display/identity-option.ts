export interface IdentityOptionLike {
  extra?: null | Record<string, unknown>;
  label?: string;
  value?: number | string;
  [key: string]: unknown;
}

export interface IdentityOptionResolverConfig {
  avatarField?: string;
  displayFallbackFields?: string[];
  displayField?: string;
  secondaryFallbackFields?: string[];
  secondaryField?: string;
  tagFallbackFields?: string[];
  tagField?: string;
}

export interface ResolvedIdentityOption {
  architectureLabel: string;
  avatar: string;
  displayName: string;
  fallbackLabel: string;
  secondaryText: string;
  value: number | string | undefined;
}

function getNestedValue(
  record: Record<string, unknown>,
  path: string,
): unknown {
  if (!path) return undefined;

  let current: unknown = record;
  for (const segment of path.split('.')) {
    current = (current as Record<string, unknown>)?.[segment];
  }
  return current;
}

function getExtraRecord(option: IdentityOptionLike): Record<string, unknown> {
  return option.extra && typeof option.extra === 'object' ? option.extra : {};
}

function getFieldValue(option: IdentityOptionLike, field: string): unknown {
  if (!field) return undefined;

  const source = option as Record<string, unknown>;
  const directValue = getNestedValue(source, field);
  if (directValue !== undefined && directValue !== null && directValue !== '') {
    return directValue;
  }

  if (field.startsWith('extra.')) {
    return undefined;
  }

  const extra = getExtraRecord(option);
  return getNestedValue(extra, field);
}

function getFirstStringValue(
  option: IdentityOptionLike,
  fields: string[],
): string {
  for (const field of fields) {
    const value = getFieldValue(option, field);
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return '';
}

export function resolveIdentityOption(
  option: IdentityOptionLike,
  config: IdentityOptionResolverConfig = {},
): ResolvedIdentityOption {
  const avatarField = config.avatarField ?? 'avatar';
  const displayField = config.displayField ?? 'nickname';
  const secondaryField = config.secondaryField ?? 'username';
  const tagField = config.tagField ?? 'orgNodeName';

  const displayFields = [
    displayField,
    ...(config.displayFallbackFields ?? [
      'display_name',
      'displayName',
      'real_name',
      'realName',
      'label',
      'username',
    ]),
  ];
  const secondaryFields = [
    secondaryField,
    ...(config.secondaryFallbackFields ?? ['email']),
  ];
  const tagFields = [
    tagField,
    ...(config.tagFallbackFields ?? ['org_node_name']),
  ];

  const displayName = getFirstStringValue(option, displayFields);
  const fallbackLabel = getFirstStringValue(option, ['label']) || displayName;
  const secondaryText = getFirstStringValue(option, secondaryFields);
  const architectureLabel = getFirstStringValue(option, tagFields);
  const avatar = getFirstStringValue(option, [avatarField]);

  return {
    architectureLabel,
    avatar,
    displayName: displayName || fallbackLabel || secondaryText,
    fallbackLabel,
    secondaryText:
      secondaryText && secondaryText !== displayName ? secondaryText : '',
    value:
      typeof option.value === 'number' || typeof option.value === 'string'
        ? option.value
        : undefined,
  };
}
