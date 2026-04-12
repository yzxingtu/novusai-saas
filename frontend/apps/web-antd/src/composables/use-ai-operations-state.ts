import type { EnhancedFormFieldDescriptor } from './ai-operation-types';
import type { FormState, TrackableFormApi } from './use-form-state-tracker';

import { formStateTracker } from './use-form-state-tracker';

// ============ Dot-path helpers for nested form fields / 点号路径工具函数 ============

/**
 * Convert flat dot-notation keys to a nested object structure / 将扁平点号键转为嵌套对象
 * Non-dot keys are kept as-is.
 * e.g. { 'quota.max_users': 5, name: 'x' } => { quota: { max_users: 5 }, name: 'x' }
 */
export function expandDotKeys(
  flat: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(flat)) {
    if (!key.includes('.')) {
      result[key] = value;
      continue;
    }
    const parts = key.split('.');
    let current = result as Record<string, any>;
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!part) {
        continue;
      }
      current[part] = current[part] ?? {};
      current = current[part];
    }
    const lastPart = parts.at(-1);
    if (lastPart) {
      current[lastPart] = value;
    }
  }
  return result;
}

/**
 * Read a value from a nested object using a dot-separated path / 按点号路径从嵌套对象取值
 * e.g. getByDotPath({ quota: { max_users: 5 } }, 'quota.max_users') => 5
 */
function getByDotPath(obj: Record<string, unknown>, path: string): unknown {
  if (!path.includes('.')) return obj[path];
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (
      current === null ||
      current === undefined ||
      typeof current !== 'object'
    )
      return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

export function isFormOpen(pageKey: string): boolean {
  return formStateTracker.isOpenWithFallback(pageKey);
}

export function getFormApi(pageKey: string): TrackableFormApi | null {
  return formStateTracker.getFormApi(pageKey);
}

export async function getFormState(pageKey: string): Promise<FormState> {
  return formStateTracker.getStateWithFallback(pageKey);
}

function sanitizeRemoteSelectScalarValue(
  fieldName: string,
  expectedType: EnhancedFormFieldDescriptor['type'],
  value: unknown,
): boolean | number | string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }

  if (expectedType === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return undefined;
    }
    if (fieldName.endsWith('_id') && value <= 0) {
      return undefined;
    }
    return value;
  }

  if (expectedType === 'boolean') {
    return typeof value === 'boolean' ? value : undefined;
  }

  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized || undefined;
}

export function sanitizeRemoteSelectOverrides(
  fieldMap: Record<string, EnhancedFormFieldDescriptor>,
  values: Record<string, unknown>,
): Record<string, unknown> {
  const sanitized: Record<string, unknown> = {};

  for (const [fieldName, value] of Object.entries(values)) {
    const descriptor = fieldMap[fieldName];
    if (!descriptor) {
      continue;
    }

    if (descriptor.component !== 'remote_select') {
      sanitized[fieldName] = value;
      continue;
    }

    if (descriptor.type === 'array') {
      if (!Array.isArray(value)) {
        continue;
      }
      const itemType = descriptor.items?.type ?? 'string';
      const normalizedItems = value
        .map((item) =>
          sanitizeRemoteSelectScalarValue(fieldName, itemType, item),
        )
        .filter(
          (item): item is boolean | number | string => item !== undefined,
        );
      if (normalizedItems.length > 0) {
        sanitized[fieldName] = normalizedItems;
      }
      continue;
    }

    const normalized = sanitizeRemoteSelectScalarValue(
      fieldName,
      descriptor.type,
      value,
    );
    if (normalized !== undefined) {
      sanitized[fieldName] = normalized;
    }
  }

  return sanitized;
}

// ============ Fill-form read-back verification / fill_form 读回验证 ============

interface FieldFeedback {
  requested: unknown;
  actual: unknown;
  match: boolean;
}

function isMeaningfullyFilled(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value as object).length > 0;
  return true;
}

/**
 * After setValues, read back actual form values and compare with the requested values / setValues 后读回表单实际值并与请求值对比
 * Returns per-field feedback so the LLM can detect
 * mismatches (e.g. passed a label instead of a value for Select fields).
 */
export async function buildFillFormFeedback(
  trackedApi: {
    getValues: () => Promise<Record<string, unknown>> | Record<string, unknown>;
  },
  requestedValues: Record<string, unknown>,
): Promise<{
  feedback: Record<string, FieldFeedback>;
  mismatchCount: number;
}> {
  let actualValues: Record<string, unknown> = {};
  try {
    actualValues = await trackedApi.getValues();
  } catch {
    // Form may not be ready — return optimistic feedback / 表单可能未就绪，返回乐观反馈
    const feedback: Record<string, FieldFeedback> = {};
    for (const [k, v] of Object.entries(requestedValues)) {
      feedback[k] = { requested: v, actual: v, match: true };
    }
    return { feedback, mismatchCount: 0 };
  }

  const feedback: Record<string, FieldFeedback> = {};
  let mismatchCount = 0;
  for (const [key, requested] of Object.entries(requestedValues)) {
    const actual = getByDotPath(actualValues, key);
    const match =
      actual === requested ||
      ((actual === null || actual === undefined) &&
        (requested === null || requested === undefined)) ||
      JSON.stringify(actual) === JSON.stringify(requested);
    feedback[key] = { requested, actual, match };
    if (!match) mismatchCount++;
  }
  return { feedback, mismatchCount };
}

export async function waitForTrackedFormState(
  pageKey: string,
  timeoutMs = 1500,
): Promise<FormState> {
  const intervalMs = 60;
  let elapsed = 0;
  let latest = await formStateTracker.getStateWithFallback(pageKey);

  while (!latest.isOpen && elapsed < timeoutMs) {
    await new Promise<void>((resolve) => {
      setTimeout(resolve, intervalMs);
    });
    elapsed += intervalMs;
    latest = await formStateTracker.getStateWithFallback(pageKey);
  }

  return latest;
}

export function collectRemainingEmptyFields(
  fieldMap: Record<string, EnhancedFormFieldDescriptor>,
  currentValues: Record<string, unknown>,
  skipKeys: Iterable<string> = [],
): string[] {
  const skipped = new Set(skipKeys);
  return Object.keys(fieldMap).filter((key) => {
    if (skipped.has(key)) return false;
    return !isMeaningfullyFilled(getByDotPath(currentValues, key));
  });
}
