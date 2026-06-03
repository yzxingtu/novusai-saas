import type {
  ReconciliationProviderPlan,
  ReconciliationRequestedScope,
  ReconciliationRun,
  ReconciliationSourceRecord,
} from '../../types';

type AllocationSummary = {
  ambiguous_items: number;
  matched_items: number;
  unmatched_items: number;
  written_charge_rows: number;
};

type AllocationAudit = {
  ambiguous_item_samples: unknown[];
  unmatched_item_samples: unknown[];
};

export function formatTimestamp(value: null | string): string {
  if (!value) return '-';
  return value.replace('T', ' ').replace('Z', '');
}

export function formatBytes(value: number): string {
  if (!value) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount >= 10 || index === 0 ? amount.toFixed(0) : amount.toFixed(2)} ${units[index]}`;
}

export function sourceAllocationSummary(
  source: ReconciliationSourceRecord,
): AllocationSummary {
  const raw = source.raw_payload_json?.allocation_summary;
  const payload =
    typeof raw === 'object' && raw !== null
      ? (raw as Partial<AllocationSummary>)
      : {};
  return {
    matched_items: Number(payload.matched_items ?? 0),
    unmatched_items: Number(payload.unmatched_items ?? 0),
    ambiguous_items: Number(payload.ambiguous_items ?? 0),
    written_charge_rows: Number(payload.written_charge_rows ?? 0),
  };
}

export function sourceAllocationAudit(
  source: ReconciliationSourceRecord,
): AllocationAudit {
  const raw = source.raw_payload_json?.allocation_audit;
  const payload =
    typeof raw === 'object' && raw !== null
      ? (raw as Partial<AllocationAudit>)
      : {};
  return {
    unmatched_item_samples: Array.isArray(payload.unmatched_item_samples)
      ? payload.unmatched_item_samples
      : [],
    ambiguous_item_samples: Array.isArray(payload.ambiguous_item_samples)
      ? payload.ambiguous_item_samples
      : [],
  };
}

export function hasAuditSamples(source: ReconciliationSourceRecord): boolean {
  const audit = sourceAllocationAudit(source);
  return (
    audit.unmatched_item_samples.length > 0 ||
    audit.ambiguous_item_samples.length > 0
  );
}

export function normalizeNumber(value: unknown): null | number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function runRequestedScope(
  run: ReconciliationRun,
): ReconciliationRequestedScope {
  return typeof run.requested_scope === 'object' && run.requested_scope !== null
    ? (run.requested_scope as ReconciliationRequestedScope)
    : {};
}

export function stringifyScopeValue(value: unknown): null | string {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return null;
}

export function scopeProviderCodes(
  scope: ReconciliationRequestedScope,
): string[] {
  const raw = scope.provider_codes;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => stringifyScopeValue(item))
    .filter((item): item is string => Boolean(item));
}

export function scopeProviderPlans(
  scope: ReconciliationRequestedScope,
): ReconciliationProviderPlan[] {
  const raw = scope.provider_plans;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      if (typeof item !== 'object' || item === null) return null;
      const payload = item as Record<string, unknown>;
      const providerCode = stringifyScopeValue(payload.provider_code);
      const billingDate = stringifyScopeValue(payload.billing_date);
      if (!providerCode || !billingDate) return null;
      return {
        billing_date: billingDate,
        cron: stringifyScopeValue(payload.cron) ?? undefined,
        local_time: stringifyScopeValue(payload.local_time) ?? undefined,
        official_billing_lag_days: normalizeNumber(
          payload.official_billing_lag_days,
        ),
        official_target_rule:
          stringifyScopeValue(payload.official_target_rule) ?? undefined,
        provider_code: providerCode,
      };
    })
    .filter((item): item is ReconciliationProviderPlan => Boolean(item));
}

export function scopeProviderPlanSummary(
  scope: ReconciliationRequestedScope,
  providerLabelFromAny: (code: string) => string,
): string[] {
  return scopeProviderPlans(scope).map((plan) => {
    const label = providerLabelFromAny(plan.provider_code);
    if (plan.official_target_rule) {
      return `${label} ${plan.official_target_rule} (${plan.billing_date})`;
    }
    return `${label} (${plan.billing_date})`;
  });
}

export function selectedRunScopeSummary(
  run: ReconciliationRun,
  providerLabelFromAny: (code: string) => string,
): string {
  const scope = runRequestedScope(run);
  const parts: string[] = [];
  const job = stringifyScopeValue(scope.job);
  const billingDate = stringifyScopeValue(scope.billing_date);
  const billingMonth = stringifyScopeValue(scope.billing_month);
  const targetRule = stringifyScopeValue(scope.official_target_rule);
  const lagDays = stringifyScopeValue(scope.official_billing_lag_days);
  const scheduledProvider = stringifyScopeValue(scope.scheduled_provider_code);
  const providerCodes = scopeProviderCodes(scope);
  const providerPlans = scopeProviderPlanSummary(scope, providerLabelFromAny);

  if (job) {
    parts.push(`job=${job}`);
  }
  if (billingDate) {
    parts.push(`billing_date=${billingDate}`);
  }
  if (billingMonth) {
    parts.push(`billing_month=${billingMonth}`);
  }
  if (scheduledProvider) {
    parts.push(`scheduled_provider=${providerLabelFromAny(scheduledProvider)}`);
  }
  if (providerCodes.length) {
    parts.push(
      `providers=${providerCodes.map((code) => providerLabelFromAny(code)).join(', ')}`,
    );
  }
  if (targetRule) {
    parts.push(`rule=${targetRule}`);
  }
  if (lagDays) {
    parts.push(`lag=${lagDays}`);
  }
  if (providerPlans.length) {
    parts.push(`plans=${providerPlans.join(' / ')}`);
  }
  return parts.join(' | ') || '-';
}

export function selectedRunScopePayload(run: ReconciliationRun): string {
  return JSON.stringify(runRequestedScope(run), null, 2);
}
