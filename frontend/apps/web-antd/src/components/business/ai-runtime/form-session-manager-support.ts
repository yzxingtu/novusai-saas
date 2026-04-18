import type {
  FormFieldDescriptor,
  FormRecordId,
  FormSession,
  FormSessionMode,
  FormSessionStage,
  InferEntityNameInput,
  InferFormModeInput,
} from './form-session-manager-types';

export interface SessionEntry {
  fieldsByName: Map<string, FormFieldDescriptor>;
  remainingRequired: Set<string>;
  touchedFields: Set<string>;
  writableFieldCount: number;
  session: FormSession;
}

const URL_BASE = 'https://novusai.local';
const URL_MODE_PATTERNS = {
  create: /(^|\/)(create|new)(\/|$)|[?&](action|mode)=create/i,
  edit: /(^|\/)edit(\/|$)|\/\d+\/edit(\/|$)|[?&](action|mode)=edit/i,
  view: /(^|\/)(detail|view)(\/|$)|[?&](action|mode)=view/i,
};

export function cloneFieldDescriptor(
  field: FormFieldDescriptor,
  fallbackValue?: unknown,
): FormFieldDescriptor {
  return {
    ...field,
    value: field.value ?? fallbackValue,
  };
}

export function normalizeFieldName(name: string): string {
  return name.trim();
}

function normalizePath(url?: string): string {
  if (!url) return '';
  try {
    const parsed = new URL(url, URL_BASE);
    return `${parsed.pathname}${parsed.search}`.toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

export function isEmptyValue(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
}

export function hasRecordId(
  recordId: FormRecordId | null | undefined,
): boolean {
  if (recordId === null || recordId === undefined) return false;
  if (typeof recordId === 'string') return recordId.trim().length > 0;
  return true;
}

function hasAnyValue(values?: Record<string, unknown>): boolean {
  if (!values) return false;
  return Object.values(values).some((value) => !isEmptyValue(value));
}

function singularize(segment: string): string {
  const lower = segment.toLowerCase();
  if (lower.endsWith('ies') && lower.length > 3) {
    return `${lower.slice(0, -3)}y`;
  }
  if (lower.endsWith('ses') && lower.length > 3) {
    return lower.slice(0, -2);
  }
  if (lower.endsWith('s') && lower.length > 1) {
    return lower.slice(0, -1);
  }
  return lower;
}

function inferEntityFromPath(path: string): null | string {
  const [pathPart = ''] = path.split('?');
  const segments = pathPart
    .split('/')
    .map((segment) => segment.trim())
    .filter(Boolean)
    .filter((segment) => !/^\d+$/.test(segment))
    .filter(
      (segment) =>
        ![
          'admin',
          'create',
          'detail',
          'edit',
          'new',
          'tenant',
          'user',
          'view',
        ].includes(segment),
    );
  const last = segments.at(-1);
  return last ? singularize(last) : null;
}

function inferRecordIdFromPath(path: string): FormRecordId | null {
  const match = path.match(/\/(\d+)(?=\/(?:edit|view|detail)|$)/i);
  if (!match || !match[1]) return null;
  return Number(match[1]);
}

function inferRecordIdFromValues(
  currentValues?: Record<string, unknown>,
  initialValues?: Record<string, unknown>,
): FormRecordId | null {
  for (const source of [currentValues, initialValues]) {
    if (!source) continue;
    const candidate =
      source.record_id ??
      source.recordId ??
      source.id ??
      source.ID ??
      source.Id;
    if (hasRecordId(candidate as FormRecordId | null | undefined)) {
      return candidate as FormRecordId;
    }
  }
  return null;
}

export function inferEntityName(input: InferEntityNameInput): string {
  if (input.entity_name?.trim()) {
    return input.entity_name.trim();
  }

  if (input.form_name?.trim()) {
    const fromForm = input.form_name
      .replace(/Form$/i, '')
      .replaceAll('-', '_')
      .trim();
    if (fromForm) {
      return fromForm.toLowerCase();
    }
  }

  const inferredFromPath = inferEntityFromPath(
    normalizePath(input.current_url),
  );
  return inferredFromPath ?? 'unknown_entity';
}

export function inferFormMode(input: InferFormModeInput): FormSessionMode {
  const path = normalizePath(input.current_url);

  if (URL_MODE_PATTERNS.create.test(path)) {
    return 'create';
  }
  if (URL_MODE_PATTERNS.edit.test(path)) {
    return input.readonly ? 'view' : 'edit';
  }
  if (URL_MODE_PATTERNS.view.test(path)) {
    return 'view';
  }
  if (hasRecordId(input.record_id)) {
    return input.readonly ? 'view' : 'edit';
  }
  if (input.readonly) {
    return 'view';
  }

  const hasSeedValues =
    hasAnyValue(input.initial_values) || hasAnyValue(input.current_values);
  if (hasSeedValues) {
    return 'edit';
  }

  const hasKnownValues =
    input.initial_values !== undefined || input.current_values !== undefined;
  if (hasKnownValues) {
    return 'create';
  }

  return 'unknown';
}

export function toSessionMode(mode: 'add' | FormSessionMode): FormSessionMode {
  return mode === 'add' ? 'create' : mode;
}

export function isWritableField(field: FormFieldDescriptor): boolean {
  return !field.disabled && !field.readonly;
}

export function computeRuntimeStage(entry: SessionEntry): FormSessionStage {
  const { session } = entry;

  if (session.stage === 'submitting' || session.stage === 'submitted') {
    return session.stage;
  }

  if (session.mode === 'view') {
    return 'ready';
  }
  if (session.can_submit) {
    return 'ready_to_submit';
  }
  if (entry.touchedFields.size > 0) {
    return 'filled_partial';
  }
  return 'ready';
}

export function computeCanSubmit(entry: SessionEntry): boolean {
  const { session } = entry;
  if (session.submit_policy === 'off') return false;
  if (session.mode === 'view') return false;
  if (entry.writableFieldCount === 0) return false;
  return entry.remainingRequired.size === 0;
}

export function toSortedArray(values: Set<string>): string[] {
  return [...values].toSorted((left, right) => left.localeCompare(right));
}

export function inferSessionRecordId(input: {
  currentValues: Record<string, unknown>;
  existingRecordId?: FormRecordId | null;
  initialValues: Record<string, unknown>;
  inputRecordId?: FormRecordId | null;
  normalizedPath: string;
}): FormRecordId | null {
  return (
    input.inputRecordId ??
    input.existingRecordId ??
    inferRecordIdFromValues(input.currentValues, input.initialValues) ??
    inferRecordIdFromPath(input.normalizedPath)
  );
}

export function normalizeSessionPath(url?: string): string {
  return normalizePath(url);
}
