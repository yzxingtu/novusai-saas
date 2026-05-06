import type {
  PeriodicTaskBindingInfo,
  PeriodicTaskBindingUpdatePayload,
} from '#/api/admin/periodic-task';

type TenantOptionLike = {
  label: string;
  value: number | string;
};

export interface TaskBindingOverrideDraft {
  configOverrideText: string;
  cronExpressionOverride: string;
  disabledReason: string;
  effectiveCronExpression: null | string;
  effectiveIntervalSeconds: null | number;
  effectiveScheduleType: null | string;
  intervalSecondsOverride: null | number;
  isEnabled: boolean;
  kwargsOverrideText: string;
  scheduleTypeOverride: null | string;
  tenantId: number;
  tenantName: string;
}

export interface TaskBindingOverridePayloadResult {
  errors: Array<'config' | 'kwargs'>;
  payload: PeriodicTaskBindingUpdatePayload;
}

function toJsonText(value: null | Record<string, unknown> | undefined): string {
  return value ? JSON.stringify(value, null, 2) : '';
}

function tenantNameFromOptions(
  tenantId: number,
  options: TenantOptionLike[],
): string {
  const matched = options.find((item) => Number(item.value) === tenantId);
  return matched?.label ?? `#${tenantId}`;
}

export function createBindingOverrideDraft(
  tenantId: number,
  tenantName: string,
  binding?: PeriodicTaskBindingInfo,
  defaultIsEnabled = true,
): TaskBindingOverrideDraft {
  return {
    tenantId,
    tenantName,
    isEnabled: binding?.isEnabled ?? defaultIsEnabled,
    disabledReason: binding?.disabledReason ?? '',
    scheduleTypeOverride: binding?.scheduleTypeOverride ?? null,
    cronExpressionOverride: binding?.cronExpressionOverride ?? '',
    intervalSecondsOverride: binding?.intervalSecondsOverride ?? null,
    kwargsOverrideText: toJsonText(binding?.kwargsOverride),
    configOverrideText: toJsonText(binding?.configOverride),
    effectiveScheduleType: binding?.effectiveScheduleType ?? null,
    effectiveCronExpression: binding?.effectiveCronExpression ?? null,
    effectiveIntervalSeconds: binding?.effectiveIntervalSeconds ?? null,
  };
}

export function reconcileBindingOverrideDrafts(
  previousDrafts: TaskBindingOverrideDraft[],
  selectedTenantIds: number[],
  tenantOptions: TenantOptionLike[],
  bindings: PeriodicTaskBindingInfo[],
  defaultIsEnabled = true,
): TaskBindingOverrideDraft[] {
  const previousMap = new Map(
    previousDrafts.map((draft) => [draft.tenantId, draft]),
  );
  const bindingMap = new Map(
    bindings.map((binding) => [binding.tenantId, binding]),
  );

  return selectedTenantIds.map((tenantId) => {
    const previous = previousMap.get(tenantId);
    if (previous) {
      return {
        ...previous,
        tenantName: tenantNameFromOptions(tenantId, tenantOptions),
      };
    }
    return createBindingOverrideDraft(
      tenantId,
      tenantNameFromOptions(tenantId, tenantOptions),
      bindingMap.get(tenantId),
      defaultIsEnabled,
    );
  });
}

function parseJsonObject(
  text: string,
): { ok: false } | { ok: true; value: null | Record<string, unknown> } {
  const trimmed = text.trim();
  if (!trimmed) {
    return { ok: true, value: null };
  }
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      return { ok: false };
    }
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch {
    return { ok: false };
  }
}

export function toBindingOverridePayload(
  draft: TaskBindingOverrideDraft,
): TaskBindingOverridePayloadResult {
  const kwargs = parseJsonObject(draft.kwargsOverrideText);
  const config = parseJsonObject(draft.configOverrideText);
  const errors: Array<'config' | 'kwargs'> = [];

  if (!kwargs.ok) {
    errors.push('kwargs');
  }
  if (!config.ok) {
    errors.push('config');
  }

  return {
    errors,
    payload: {
      tenantId: draft.tenantId,
      isEnabled: draft.isEnabled,
      disabledReason: draft.isEnabled
        ? null
        : draft.disabledReason.trim() || null,
      scheduleTypeOverride: draft.scheduleTypeOverride,
      cronExpressionOverride:
        draft.scheduleTypeOverride === 'cron'
          ? draft.cronExpressionOverride.trim() || null
          : null,
      intervalSecondsOverride:
        draft.scheduleTypeOverride === 'interval'
          ? draft.intervalSecondsOverride
          : null,
      kwargsOverride: kwargs.ok ? kwargs.value : undefined,
      configOverride: config.ok ? config.value : undefined,
    },
  };
}
