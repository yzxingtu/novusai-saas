/**
 * DataForge Studio Plugin - Type definitions
 */

// ── Domain types ─────────────────────────────────────────────────────────────

export interface NccField {
  name: string;
  type: 'boolean' | 'datetime' | 'integer' | 'json' | 'string' | 'text';
  label: string;
  required: boolean;
  default: unknown;
  options?: string[];
}

export interface NccSchemaConfig {
  fields: NccField[];
}

export interface NccProject {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  color?: string;
  icon?: string;
  created_at: string;
  updated_at: string;
}

export interface NccTableSchema {
  id: number;
  project_id: number;
  name: string;
  display_name: string;
  description?: string;
  schema_config: NccSchemaConfig;
  form_config: Record<string, unknown>;
  ui_config: Record<string, unknown>;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface NccRelation {
  id: number;
  project_id: number;
  from_schema_id: number;
  to_schema_id: number;
  from_field: string;
  to_field: string;
  relation_type: string;
  label?: string;
}

export interface NccRecord {
  id: number;
  schema_id: number;
  project_id: number;
  data: Record<string, unknown>;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export type FormWidgetType =
  | 'input' | 'password' | 'email' | 'url'
  | 'number' | 'slider' | 'rate'
  | 'select' | 'radio' | 'checkbox-group'
  | 'switch' | 'checkbox'
  | 'date' | 'datetime' | 'time'
  | 'textarea'
  | 'upload'
  | 'json-editor'
  | 'divider';

export interface FormField {
  id: string;
  name: string;
  label: string;
  type: NccField['type'];
  widget: FormWidgetType;
  required: boolean;
  placeholder: string;
  helpText: string;
  options: string[];
  span: 12 | 24;
  defaultValue: string;
  disabled: boolean;
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  step?: number;
  rows?: number;
  pattern?: string;
  multiple?: boolean;
  locales?: Record<string, { label?: string; placeholder?: string; helpText?: string }>;
}

// ── Plugin shared API type ───────────────────────────────────────────────────

export interface NovusPluginSharedAPI {
  $t: (key: string, ...args: unknown[]) => string;
  requestClient: {
    get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
    put: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
    delete: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
  };
  IconifyIcon: unknown;
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
  router?: { push: (to: unknown) => void };
}
