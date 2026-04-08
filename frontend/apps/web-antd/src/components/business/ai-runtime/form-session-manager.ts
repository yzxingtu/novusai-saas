export type FormRecordId = number | string;

export type FormSessionMode = 'create' | 'edit' | 'unknown' | 'view';
export type FormSessionStage =
  | 'failed'
  | 'filled_partial'
  | 'opening'
  | 'ready'
  | 'ready_to_submit'
  | 'submitted'
  | 'submitting';
export type FormSubmitPolicy = 'auto' | 'confirm' | 'off';

export interface FormFieldDescriptor {
  name: string;
  label?: string;
  required?: boolean;
  disabled?: boolean;
  readonly?: boolean;
  type?: string;
  value?: unknown;
  initialValue?: unknown;
  options?: Array<{ label: string; value: unknown }>;
}

export interface FormSession {
  form_session_id: string;
  surface_id: string;
  entity_name: string;
  mode: FormSessionMode;
  stage: FormSessionStage;
  record_id: FormRecordId | null;
  remaining_required_fields: string[];
  can_submit: boolean;
  submit_policy: FormSubmitPolicy;
  fields: FormFieldDescriptor[];
  created_at: number;
  updated_at: number;
}

export interface InferEntityNameInput {
  current_url?: string;
  entity_name?: string;
  form_name?: string;
}

export interface InferFormModeInput {
  current_url?: string;
  record_id?: FormRecordId | null;
  readonly?: boolean;
  initial_values?: Record<string, unknown>;
  current_values?: Record<string, unknown>;
}

export interface UpsertFormSessionInput {
  form_session_id?: string;
  surface_id: string;
  entity_name?: string;
  form_name?: string;
  mode?: FormSessionMode;
  stage?: FormSessionStage;
  record_id?: FormRecordId | null;
  fields?: FormFieldDescriptor[];
  submit_policy?: FormSubmitPolicy;
  readonly?: boolean;
  current_url?: string;
  initial_values?: Record<string, unknown>;
  current_values?: Record<string, unknown>;
}

interface SessionEntry {
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

function cloneFieldDescriptor(
  field: FormFieldDescriptor,
  fallbackValue?: unknown,
): FormFieldDescriptor {
  return {
    ...field,
    value: field.value ?? fallbackValue,
  };
}

function normalizeFieldName(name: string): string {
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

function isEmptyValue(value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
}

function hasRecordId(recordId: FormRecordId | null | undefined): boolean {
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

function inferEntityFromPath(path: string): string | null {
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
  const match = path.match(/\/(\d+)(?=\/(edit|view|detail)|$)/i);
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
      .replace(/-/g, '_')
      .trim();
    if (fromForm) {
      return fromForm.toLowerCase();
    }
  }

  const inferredFromPath = inferEntityFromPath(normalizePath(input.current_url));
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

function toSessionMode(mode: FormSessionMode | 'add'): FormSessionMode {
  return mode === 'add' ? 'create' : mode;
}

function isWritableField(field: FormFieldDescriptor): boolean {
  return !field.disabled && !field.readonly;
}

function computeRuntimeStage(entry: SessionEntry): FormSessionStage {
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

function computeCanSubmit(entry: SessionEntry): boolean {
  const { session } = entry;
  if (session.submit_policy === 'off') return false;
  if (session.mode === 'view') return false;
  if (entry.writableFieldCount === 0) return false;
  return entry.remainingRequired.size === 0;
}

function toSortedArray(values: Set<string>): string[] {
  return [...values].sort((left, right) => left.localeCompare(right));
}

export class FormSessionManager {
  private activeSessionId: null | string = null;
  private activeSessionBySurfaceId = new Map<string, string>();
  private counter = 0;
  private sessions = new Map<string, SessionEntry>();

  clear(): void {
    this.sessions.clear();
    this.activeSessionBySurfaceId.clear();
    this.activeSessionId = null;
  }

  closeSession(formSessionId: string): void {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return;

    this.sessions.delete(formSessionId);
    if (this.activeSessionId === formSessionId) {
      this.activeSessionId = null;
    }
    if (
      this.activeSessionBySurfaceId.get(entry.session.surface_id) ===
      formSessionId
    ) {
      this.activeSessionBySurfaceId.delete(entry.session.surface_id);
    }
  }

  getActiveFieldDescriptors(surfaceId?: string): FormFieldDescriptor[] {
    return this.getActiveSession(surfaceId)?.fields ?? [];
  }

  getActiveSession(surfaceId?: string): FormSession | null {
    if (surfaceId) {
      const activeBySurface = this.activeSessionBySurfaceId.get(surfaceId);
      if (!activeBySurface) return null;
      return this.getSession(activeBySurface);
    }

    if (!this.activeSessionId) return null;
    return this.getSession(this.activeSessionId);
  }

  getFieldDescriptor(
    formSessionId: string,
    fieldName: string,
  ): FormFieldDescriptor | null {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return null;
    const descriptor = entry.fieldsByName.get(fieldName);
    return descriptor ? { ...descriptor } : null;
  }

  getSession(formSessionId: string): FormSession | null {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return null;
    return {
      ...entry.session,
      fields: entry.session.fields.map((field) => ({ ...field })),
      remaining_required_fields: [...entry.session.remaining_required_fields],
    };
  }

  listSessions(): FormSession[] {
    const snapshots: FormSession[] = [];
    for (const entry of this.sessions.values()) {
      const snapshot = this.getSession(entry.session.form_session_id);
      if (snapshot) {
        snapshots.push(snapshot);
      }
    }
    return snapshots;
  }

  markFailed(formSessionId: string): FormSession | null {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return null;
    entry.session.stage = 'failed';
    entry.session.updated_at = Date.now();
    return this.getSession(formSessionId);
  }

  markSubmitted(formSessionId: string): FormSession | null {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return null;
    entry.session.stage = 'submitted';
    entry.session.updated_at = Date.now();
    return this.getSession(formSessionId);
  }

  markSubmitting(formSessionId: string): FormSession | null {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return null;
    entry.session.stage = 'submitting';
    entry.session.updated_at = Date.now();
    return this.getSession(formSessionId);
  }

  setActiveSession(formSessionId: string): void {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return;
    this.activeSessionId = formSessionId;
    this.activeSessionBySurfaceId.set(entry.session.surface_id, formSessionId);
  }

  updateFieldValues(
    formSessionId: string,
    values: Record<string, unknown>,
  ): FormSession | null {
    const entry = this.sessions.get(formSessionId);
    if (!entry) return null;

    for (const [rawName, nextValue] of Object.entries(values)) {
      const name = normalizeFieldName(rawName);
      const descriptor =
        entry.fieldsByName.get(name) ??
        ({
          name,
        } satisfies FormFieldDescriptor);

      const initialValue = descriptor.initialValue;
      descriptor.value = nextValue;
      entry.fieldsByName.set(name, descriptor);

      const required = !!descriptor.required && isWritableField(descriptor);
      if (required) {
        if (isEmptyValue(nextValue)) {
          entry.remainingRequired.add(name);
        } else {
          entry.remainingRequired.delete(name);
        }
      }

      if (
        nextValue === initialValue ||
        (isEmptyValue(nextValue) && isEmptyValue(initialValue))
      ) {
        entry.touchedFields.delete(name);
      } else {
        entry.touchedFields.add(name);
      }
    }

    this.commitComputedState(entry);
    return this.getSession(formSessionId);
  }

  upsertSession(input: UpsertFormSessionInput): FormSession {
    const now = Date.now();
    const formSessionId = input.form_session_id ?? `form_${++this.counter}`;
    const existing = this.sessions.get(formSessionId);
    const submitPolicy =
      input.submit_policy ?? existing?.session.submit_policy ?? 'confirm';
    const fieldsInput = input.fields ?? existing?.session.fields ?? [];
    const currentValues = input.current_values ?? {};
    const initialValues = input.initial_values ?? {};
    const fieldsByName = new Map<string, FormFieldDescriptor>();
    const remainingRequired = new Set<string>();
    const touchedFields = new Set<string>();
    let writableFieldCount = 0;

    for (const rawField of fieldsInput) {
      const name = normalizeFieldName(rawField.name);
      if (!name) continue;

      const value =
        rawField.value ??
        currentValues[name] ??
        existing?.fieldsByName.get(name)?.value;
      const initialValue =
        rawField.initialValue ??
        initialValues[name] ??
        existing?.fieldsByName.get(name)?.initialValue;
      const descriptor = cloneFieldDescriptor(
        {
          ...rawField,
          name,
          initialValue,
        },
        value,
      );
      fieldsByName.set(name, descriptor);

      const writable = isWritableField(descriptor);
      if (writable) {
        writableFieldCount += 1;
      }

      if (descriptor.required && writable && isEmptyValue(descriptor.value)) {
        remainingRequired.add(name);
      }

      if (
        !(
          descriptor.value === initialValue ||
          (isEmptyValue(descriptor.value) && isEmptyValue(initialValue))
        )
      ) {
        touchedFields.add(name);
      }
    }

    const normalizedPath = normalizePath(input.current_url);
    const recordId =
      input.record_id ??
      existing?.session.record_id ??
      inferRecordIdFromValues(currentValues, initialValues) ??
      inferRecordIdFromPath(normalizedPath);
    const mode =
      toSessionMode(
        input.mode ??
          inferFormMode({
            current_url: input.current_url,
            record_id: recordId,
            readonly: input.readonly,
            initial_values: initialValues,
            current_values: currentValues,
          }),
      );

    const session: FormSession = {
      form_session_id: formSessionId,
      surface_id: input.surface_id,
      entity_name: inferEntityName({
        current_url: input.current_url,
        entity_name: input.entity_name,
        form_name: input.form_name,
      }),
      mode,
      stage: input.stage ?? 'opening',
      record_id: hasRecordId(recordId) ? (recordId as FormRecordId) : null,
      remaining_required_fields: [],
      can_submit: false,
      submit_policy: submitPolicy,
      fields: [...fieldsByName.values()],
      created_at: existing?.session.created_at ?? now,
      updated_at: now,
    };

    const entry: SessionEntry = {
      fieldsByName,
      remainingRequired,
      touchedFields,
      writableFieldCount,
      session,
    };
    this.commitComputedState(entry, input.stage);
    this.sessions.set(formSessionId, entry);
    this.activeSessionId = formSessionId;
    this.activeSessionBySurfaceId.set(input.surface_id, formSessionId);
    return this.getSession(formSessionId)!;
  }

  private commitComputedState(
    entry: SessionEntry,
    stageOverride?: FormSessionStage,
  ): void {
    entry.session.fields = [...entry.fieldsByName.values()].map((field) => ({
      ...field,
    }));
    entry.session.can_submit = computeCanSubmit(entry);
    entry.session.remaining_required_fields = toSortedArray(entry.remainingRequired);
    entry.session.stage = stageOverride ?? computeRuntimeStage(entry);
    entry.session.updated_at = Date.now();
  }
}
