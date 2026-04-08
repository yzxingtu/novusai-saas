import type {
  FormFieldDescriptor,
  FormRecordId,
  FormSessionMode,
  UpsertFormSessionInput,
} from '../form-session-manager';

export interface VbenFormRuleLike {
  required?: boolean;
}

export interface VbenFormSchemaLike {
  fieldName?: string;
  label?: string;
  required?: boolean;
  rules?: VbenFormRuleLike[];
  component?: string;
  componentProps?: Record<string, unknown>;
  defaultValue?: unknown;
}

export interface BuildVbenFormSessionInputOptions {
  form_session_id?: string;
  surface_id: string;
  entity_name?: string;
  form_name?: string;
  mode?: FormSessionMode;
  record_id?: FormRecordId | null;
  submit_policy?: UpsertFormSessionInput['submit_policy'];
  readonly?: boolean;
  current_url?: string;
  current_values?: Record<string, unknown>;
  initial_values?: Record<string, unknown>;
  schema: VbenFormSchemaLike[];
}

function toBoolean(value: unknown): boolean {
  return value === true;
}

function buildDescriptor(
  field: VbenFormSchemaLike,
  currentValues?: Record<string, unknown>,
  initialValues?: Record<string, unknown>,
): FormFieldDescriptor | null {
  const fieldName = field.fieldName?.trim();
  if (!fieldName) return null;

  const componentProps =
    field.componentProps && typeof field.componentProps === 'object'
      ? field.componentProps
      : {};

  const isReadonly = toBoolean(componentProps.readonly);
  const isDisabled = toBoolean(componentProps.disabled);

  return {
    name: fieldName,
    label: field.label ?? fieldName,
    required: !!field.required || !!field.rules?.some((rule) => !!rule.required),
    disabled: isDisabled,
    readonly: isReadonly,
    type: field.component?.toLowerCase(),
    value:
      currentValues?.[fieldName] ??
      field.defaultValue ??
      initialValues?.[fieldName],
    initialValue: initialValues?.[fieldName] ?? field.defaultValue,
  };
}

export function buildVbenFieldDescriptors(
  schema: VbenFormSchemaLike[],
  currentValues?: Record<string, unknown>,
  initialValues?: Record<string, unknown>,
): FormFieldDescriptor[] {
  const descriptors: FormFieldDescriptor[] = [];
  for (const field of schema) {
    const descriptor = buildDescriptor(field, currentValues, initialValues);
    if (descriptor) {
      descriptors.push(descriptor);
    }
  }
  return descriptors;
}

export function createVbenFormSessionInput(
  options: BuildVbenFormSessionInputOptions,
): UpsertFormSessionInput {
  const hasReadonlySchemaField = options.schema.some((field) =>
    toBoolean(field.componentProps?.readonly),
  );

  return {
    form_session_id: options.form_session_id,
    surface_id: options.surface_id,
    entity_name: options.entity_name,
    form_name: options.form_name,
    mode: options.mode,
    record_id: options.record_id,
    submit_policy: options.submit_policy,
    readonly: options.readonly ?? hasReadonlySchemaField,
    current_url: options.current_url,
    current_values: options.current_values,
    initial_values: options.initial_values,
    fields: buildVbenFieldDescriptors(
      options.schema,
      options.current_values,
      options.initial_values,
    ),
  };
}
