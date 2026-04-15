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
