import type { FormFieldDescriptor, FormSession } from './form-session-manager';

import { nextTick } from 'vue';

import { formStateTracker } from '#/composables/use-form-state-tracker';

import { tAiRuntime } from './i18n';
import {
  queryElementByLocator,
  resolveRuntimePageKey,
  type RuntimeFormActionResult,
} from './runtime-bridge-core';
import { resolveActiveFormSessionForPage } from './runtime-bridge-snapshot';
import { readValueForAI, resolveAISecurityPolicy } from './security-policy';

function resolveFormSession(formSessionId?: string): null | FormSession {
  if (formSessionId?.trim()) {
    return formStateTracker.getSession(formSessionId.trim());
  }
  return resolveActiveFormSessionForPage(resolveRuntimePageKey());
}

function serializeFormField(field: FormFieldDescriptor): Record<string, unknown> {
  const element =
    queryElementByLocator(`name:${field.name}`) ??
    queryElementByLocator(`id:${field.name}`);
  const decision = resolveAISecurityPolicy({
    element,
    fieldName: field.name,
    fieldType: field.type,
  });
  const safeValue = readValueForAI(field.value, decision);
  return {
    disabled: !!field.disabled,
    label: field.label,
    name: field.name,
    readonly: !!field.readonly,
    required: !!field.required,
    type: field.type,
    ...(safeValue !== undefined ? { value: safeValue } : {}),
  };
}

function buildFormStateData(session: FormSession): Record<string, unknown> {
  return {
    can_submit: session.can_submit,
    entity_name: session.entity_name,
    fields: session.fields.map((field) => serializeFormField(field)),
    form_session_id: session.form_session_id,
    mode: session.mode,
    record_id: session.record_id ?? undefined,
    remaining_required_fields: [...session.remaining_required_fields],
    stage: session.stage,
    submit_policy: session.submit_policy,
  };
}

async function applyFormValues(
  updates: Record<string, unknown>,
  formSessionId?: string,
): Promise<RuntimeFormActionResult> {
  const session = resolveFormSession(formSessionId);
  if (!session) {
    return {
      error: tAiRuntime('noActiveFormSessionFound'),
      error_type: 'form_session_not_found',
      message: tAiRuntime('noActiveFormAvailable'),
      success: false,
    };
  }

  const formApi = formStateTracker.getFormApi(session.form_session_id);
  if (!formApi) {
    return {
      error: tAiRuntime('formApiUnavailable'),
      error_type: 'form_api_unavailable',
      message: tAiRuntime('currentFormNotReady'),
      success: false,
    };
  }

  const fieldsByName = new Map(session.fields.map((field) => [field.name, field]));
  const writableUpdates: Record<string, unknown> = {};
  const fieldsFailed: Array<{ field: string; error: string }> = [];

  for (const [fieldName, value] of Object.entries(updates)) {
    const descriptor = fieldsByName.get(fieldName);
    if (!descriptor) {
      fieldsFailed.push({ field: fieldName, error: 'field_not_found' });
      continue;
    }
    if (descriptor.disabled || descriptor.readonly) {
      fieldsFailed.push({ field: fieldName, error: 'field_not_writable' });
      continue;
    }
    writableUpdates[fieldName] = value;
  }

  if (Object.keys(writableUpdates).length === 0) {
    return {
      data: {
        fields_failed: fieldsFailed,
        form_session: buildFormStateData(session),
      },
      error: tAiRuntime('noWritableFieldsProvided'),
      error_type: 'no_writable_fields',
      message: tAiRuntime('noWritableFieldsUpdated'),
      success: false,
    };
  }

  formApi.setValues(writableUpdates);
  await nextTick();
  let currentValues = writableUpdates;
  try {
    currentValues = await formApi.getValues();
  } catch {
    // Keep applied values when the form is still stabilizing.
  }
  const updatedSession =
    formStateTracker.setSessionFieldValues(session.form_session_id, currentValues) ??
    formStateTracker.getSession(session.form_session_id) ??
    session;

  return {
    data: {
      fields_failed: fieldsFailed,
      fields_updated: Object.keys(writableUpdates),
      form_session: buildFormStateData(updatedSession),
    },
    message:
      fieldsFailed.length > 0
        ? tAiRuntime('formFieldsUpdatedPartial')
        : tAiRuntime('formFieldsUpdated'),
    success: true,
  };
}

export async function getRuntimeFormState(
  formSessionId?: string,
): Promise<RuntimeFormActionResult> {
  const session = resolveFormSession(formSessionId);
  if (!session) {
    return {
      error: tAiRuntime('noActiveFormSessionFound'),
      error_type: 'form_session_not_found',
      message: tAiRuntime('noActiveFormAvailable'),
      success: false,
    };
  }
  return {
    data: buildFormStateData(session),
    message: tAiRuntime('formStateLoaded'),
    success: true,
  };
}

export async function setRuntimeFormField(args: {
  fieldName: string;
  formSessionId?: string;
  value: unknown;
}): Promise<RuntimeFormActionResult> {
  return applyFormValues(
    {
      [args.fieldName]: args.value,
    },
    args.formSessionId,
  );
}

export async function fillRuntimeForm(args: {
  fields: Record<string, unknown>;
  formSessionId?: string;
}): Promise<RuntimeFormActionResult> {
  return applyFormValues(args.fields, args.formSessionId);
}

export async function submitRuntimeForm(args: {
  confirm?: boolean;
  formSessionId?: string;
}): Promise<RuntimeFormActionResult> {
  const session = resolveFormSession(args.formSessionId);
  if (!session) {
    return {
      error: tAiRuntime('noActiveFormSessionFound'),
      error_type: 'form_session_not_found',
      message: tAiRuntime('noActiveFormAvailable'),
      success: false,
    };
  }
  const formApi = formStateTracker.getFormApi(session.form_session_id);
  if (!formApi?.submitForm) {
    return {
      error: tAiRuntime('formSubmitUnavailable'),
      error_type: 'form_submit_unavailable',
      message: tAiRuntime('currentFormCannotSubmit'),
      success: false,
    };
  }
  if (session.submit_policy === 'confirm' && !args.confirm) {
    return {
      data: {
        form_session: buildFormStateData(session),
      },
      error: tAiRuntime('formSubmissionRequiresConfirmation'),
      error_type: 'confirmation_required',
      message: tAiRuntime('formSubmissionRequiresConfirmation'),
      success: false,
    };
  }

  await formApi.submitForm();
  await nextTick();
  let currentValues: Record<string, unknown> = {};
  try {
    currentValues = await formApi.getValues();
  } catch {
    // Ignore when the form closes immediately after submit.
  }
  const updatedSession =
    formStateTracker.setSessionFieldValues(session.form_session_id, currentValues) ??
    formStateTracker.getSession(session.form_session_id) ??
    session;
  return {
    data: {
      form_session: buildFormStateData(updatedSession),
    },
    message: tAiRuntime('formSubmissionTriggered'),
    success: true,
  };
}
