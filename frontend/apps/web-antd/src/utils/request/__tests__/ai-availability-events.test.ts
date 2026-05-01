// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: AI account/tenant-plan 403 payloads invalidate frontend user state.
// Mock strategy: window event dispatch is real; no request or store logic is mocked.
import { describe, expect, it, vi } from 'vitest';

import {
  AI_AVAILABILITY_INVALIDATED_EVENT,
  isAIAccessDeniedPayload,
  notifyAIAccessDenied,
} from '../ai-availability-events';

describe('ai availability request events', () => {
  it('dispatches an invalidation event for account-level AI denial', () => {
    const listener = vi.fn();
    window.addEventListener(AI_AVAILABILITY_INVALIDATED_EVENT, listener);

    notifyAIAccessDenied({
      code: 4032,
      feature: 'ai_chat',
      reason: 'account_ai_disabled',
    });

    expect(listener).toHaveBeenCalledTimes(1);
    const event = listener.mock.calls[0]?.[0] as CustomEvent;
    expect(event.detail).toEqual({
      code: 4032,
      feature: 'ai_chat',
      reason: 'account_ai_disabled',
    });

    window.removeEventListener(AI_AVAILABILITY_INVALIDATED_EVENT, listener);
  });

  it('recognizes tenant-plan AI denial without matching unrelated 403 payloads', () => {
    expect(
      isAIAccessDeniedPayload({
        code: 4033,
        feature: 'ai_chat',
        reason: 'tenant_plan_ai_disabled',
      }),
    ).toBe(true);
    expect(
      isAIAccessDeniedPayload({
        code: 4030,
        reason: 'rbac_permission_denied',
      }),
    ).toBe(false);
  });
});
