import type {
  FormFieldDescriptor,
  FormRecordId,
  FormSession,
  FormSessionStage,
  UpsertFormSessionInput,
} from './form-session-manager-types';

import {
  cloneFieldDescriptor,
  computeCanSubmit,
  computeRuntimeStage,
  hasRecordId,
  inferEntityName,
  inferFormMode,
  inferSessionRecordId,
  isEmptyValue,
  isWritableField,
  normalizeFieldName,
  normalizeSessionPath,
  toSessionMode,
  toSortedArray,
  type SessionEntry,
} from './form-session-manager-support';

export type {
  FormFieldDescriptor,
  FormRecordId,
  FormSession,
  FormSessionMode,
  FormSessionStage,
  FormSubmitPolicy,
  InferEntityNameInput,
  InferFormModeInput,
  UpsertFormSessionInput,
} from './form-session-manager-types';
export { inferEntityName, inferFormMode } from './form-session-manager-support';

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

    const normalizedPath = normalizeSessionPath(input.current_url);
    const recordId = inferSessionRecordId({
      currentValues,
      existingRecordId: existing?.session.record_id,
      initialValues,
      inputRecordId: input.record_id,
      normalizedPath,
    });
    const mode = toSessionMode(
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
    return this.getSession(formSessionId) ?? {
      ...session,
      fields: session.fields.map((field) => ({ ...field })),
      remaining_required_fields: [...session.remaining_required_fields],
    };
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
