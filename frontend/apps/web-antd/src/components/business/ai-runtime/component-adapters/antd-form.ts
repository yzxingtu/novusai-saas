import type {
  FormFieldDescriptor,
  FormRecordId,
  FormSessionMode,
  UpsertFormSessionInput,
} from '../form-session-manager';

export interface AntdFormRuleLike {
  required?: boolean;
}

export interface AntdFormFieldLike {
  name: Array<number | string> | number | string;
  label?: string;
  required?: boolean;
  rules?: AntdFormRuleLike[];
  disabled?: boolean;
  readonly?: boolean;
  value?: unknown;
  initialValue?: unknown;
  type?: string;
}

export interface BuildAntdFormSessionInputOptions {
  form_session_id?: string;
  surface_id: string;
  page_key?: string;
  entity_name?: string;
  form_name?: string;
  mode?: FormSessionMode;
  record_id?: FormRecordId | null;
  submit_policy?: UpsertFormSessionInput['submit_policy'];
  readonly?: boolean;
  current_url?: string;
  current_values?: Record<string, unknown>;
  initial_values?: Record<string, unknown>;
  fields: AntdFormFieldLike[];
}

function getPathValue(
  source: Record<string, unknown> | undefined,
  path: Array<number | string>,
): unknown {
  if (!source) return undefined;
  let cursor: unknown = source;
  for (const segment of path) {
    if (!cursor || typeof cursor !== 'object') {
      return undefined;
    }
    cursor = (cursor as Record<string, unknown>)[String(segment)];
  }
  return cursor;
}

function normalizeFieldName(name: AntdFormFieldLike['name']): string {
  if (Array.isArray(name)) {
    return name.map(String).join('.');
  }
  return String(name);
}

function toPath(name: AntdFormFieldLike['name']): Array<number | string> {
  return Array.isArray(name) ? name : [name];
}

export function buildAntdFieldDescriptors(
  fields: AntdFormFieldLike[],
  currentValues?: Record<string, unknown>,
  initialValues?: Record<string, unknown>,
): FormFieldDescriptor[] {
  return fields
    .map((field) => {
      const path = toPath(field.name);
      const normalizedName = normalizeFieldName(field.name);
      const fieldValue = field.value ?? getPathValue(currentValues, path);
      const initialValue =
        field.initialValue ?? getPathValue(initialValues, path);

      return {
        name: normalizedName,
        label: field.label ?? normalizedName,
        required:
          !!field.required || !!field.rules?.some((rule) => !!rule.required),
        disabled: !!field.disabled,
        readonly: !!field.readonly,
        type: field.type,
        value: fieldValue,
        initialValue,
      } satisfies FormFieldDescriptor;
    })
    .filter((descriptor) => descriptor.name.length > 0);
}

export function createAntdFormSessionInput(
  options: BuildAntdFormSessionInputOptions,
): UpsertFormSessionInput {
  return {
    form_session_id: options.form_session_id,
    surface_id: options.surface_id,
    page_key: options.page_key,
    entity_name: options.entity_name,
    form_name: options.form_name,
    mode: options.mode,
    record_id: options.record_id,
    submit_policy: options.submit_policy,
    readonly: options.readonly,
    current_url: options.current_url,
    current_values: options.current_values,
    initial_values: options.initial_values,
    fields: buildAntdFieldDescriptors(
      options.fields,
      options.current_values,
      options.initial_values,
    ),
  };
}
