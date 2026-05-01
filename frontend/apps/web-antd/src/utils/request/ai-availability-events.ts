export const AI_AVAILABILITY_INVALIDATED_EVENT =
  'novusai:ai-availability-invalidated';

const AI_ACCESS_DENIED_CODES = new Set([4032, 4033, '4032', '4033']);
const AI_ACCESS_DENIED_REASONS = new Set([
  'account_ai_disabled',
  'leader_ai_disabled',
  'tenant_plan_ai_disabled',
]);

export interface AIAvailabilityInvalidatedDetail {
  code?: number | string;
  feature?: string;
  reason?: string;
}

export function isAIAccessDeniedPayload(payload: unknown): boolean {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  const data = payload as Record<string, unknown>;
  return (
    AI_ACCESS_DENIED_CODES.has(data.code as number | string) ||
    AI_ACCESS_DENIED_REASONS.has(String(data.reason || ''))
  );
}

export function notifyAIAccessDenied(payload: unknown): void {
  if (!isAIAccessDeniedPayload(payload) || typeof window === 'undefined') {
    return;
  }
  const data = payload as Record<string, unknown>;
  window.dispatchEvent(
    new CustomEvent<AIAvailabilityInvalidatedDetail>(
      AI_AVAILABILITY_INVALIDATED_EVENT,
      {
        detail: {
          code: data.code as number | string | undefined,
          feature: typeof data.feature === 'string' ? data.feature : undefined,
          reason: typeof data.reason === 'string' ? data.reason : undefined,
        },
      },
    ),
  );
}
