import type {
  AdminSkillPackageInfo,
  SkillPackageResolvedToolInfo,
  SkillPackageValvesInfo,
} from '#/api/admin/skill-packages';

import { $t } from '#/locales';

export type ResolvedTool = SkillPackageResolvedToolInfo;
export type ValvesSchema = NonNullable<SkillPackageValvesInfo['valves_schema']>;
export type ValvesInputType = 'json' | 'number' | 'string' | 'switch';

export interface ValveField {
  default?: unknown;
  description?: string;
  isRequired: boolean;
  key: string;
  type?: string;
}

export function getPackageStatusColor(isActive: boolean): string {
  return isActive ? 'success' : 'default';
}

export function getPackageStatusText(isActive: boolean): string {
  return isActive ? $t('admin.common.enabled') : $t('admin.common.disabled');
}

export function getPackageHeroClass(pkg: AdminSkillPackageInfo | null): string {
  if (pkg?.source_plugin) {
    return 'bg-fuchsia-500/10 text-fuchsia-600 ring-fuchsia-400/20 dark:text-fuchsia-400';
  }
  if (pkg?.is_system) {
    return 'bg-amber-500/15 text-amber-600 ring-amber-400/30 dark:text-amber-400';
  }
  return 'bg-primary/10 text-primary ring-primary/20';
}

export function getPackageIcon(icon: null | string | undefined): string {
  return icon || 'lucide:package';
}

export function getToolTypeColor(type: null | string | undefined): string {
  switch (type) {
    case 'builtin': {
      return 'purple';
    }
    case 'code_execution': {
      return 'orange';
    }
    case 'email': {
      return 'gold';
    }
    case 'http': {
      return 'blue';
    }
    default: {
      return 'default';
    }
  }
}

export function getToolTypeIcon(type: null | string | undefined): string {
  switch (type) {
    case 'builtin': {
      return 'lucide:sparkles';
    }
    case 'code_execution': {
      return 'lucide:square-terminal';
    }
    case 'email': {
      return 'lucide:mail';
    }
    case 'http': {
      return 'lucide:globe';
    }
    default: {
      return 'lucide:wrench';
    }
  }
}

export function getToolTypeText(type: null | string | undefined): string {
  if (!type) return '-';
  return type
    .replaceAll('_', ' ')
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function getToolRequiredParamCount(tool: ResolvedTool): number {
  return tool.parameters.filter((item) => item.required).length;
}

export function isSecretKey(key: string): boolean {
  const normalizedKey = key.toLowerCase().replaceAll('-', '_');
  return [
    'api_key',
    'secret',
    'password',
    'access_token',
    'auth_token',
    'private_key',
  ].some((term) => normalizedKey.includes(term));
}

export function getValveInputType(type?: string): ValvesInputType {
  switch (type) {
    case 'array':
    case 'object': {
      return 'json';
    }
    case 'boolean': {
      return 'switch';
    }
    case 'integer':
    case 'number': {
      return 'number';
    }
    default: {
      return 'string';
    }
  }
}

export function isConfiguredValveValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    return value.trim().length > 0;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === 'object') {
    return Object.keys(value).length > 0;
  }
  return true;
}

export function buildInitialValvesConfig(
  data: Pick<SkillPackageValvesInfo, 'valves_config' | 'valves_schema'>,
): Record<string, unknown> {
  const schema = data.valves_schema;
  const savedConfig = (data.valves_config || {}) as Record<string, unknown>;

  if (!schema?.properties) {
    return {};
  }

  const nextConfig: Record<string, unknown> = {};

  for (const [key, prop] of Object.entries(schema.properties)) {
    if (key in savedConfig) {
      nextConfig[key] = savedConfig[key];
      continue;
    }

    if (prop.default !== undefined) {
      nextConfig[key] = prop.default;
      continue;
    }

    switch (getValveInputType(prop.type)) {
      case 'json': {
        nextConfig[key] = prop.type === 'array' ? [] : {};
        break;
      }
      case 'number': {
        nextConfig[key] = null;
        break;
      }
      case 'switch': {
        nextConfig[key] = false;
        break;
      }
      default: {
        nextConfig[key] = '';
      }
    }
  }

  return nextConfig;
}

export function getJsonValvePlaceholder(field: ValveField): string {
  if (field.default !== undefined) {
    return JSON.stringify(field.default, null, 2);
  }
  return field.type === 'array' ? '[]' : '{}';
}

export function getSortedValveFields(
  schema: null | ValvesSchema,
): ValveField[] {
  if (!schema?.properties) {
    return [];
  }

  const required = new Set(schema.required || []);

  return Object.entries(schema.properties)
    .map(([key, prop]) => ({
      key,
      ...prop,
      isRequired: required.has(key),
    }))
    .toSorted((a, b) => {
      if (a.isRequired !== b.isRequired) {
        return a.isRequired ? -1 : 1;
      }
      return a.key.localeCompare(b.key);
    });
}
