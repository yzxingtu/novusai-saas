// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';

import {
  evaluateAIActionSecurity,
  readValueForAI,
  resolveAISecurityPolicy,
} from '../security-policy';

describe('security-policy', () => {
  it('applies mask behavior from data-ai-read=mask', () => {
    const input = document.createElement('input');
    input.setAttribute('data-ai-read', 'mask');

    const decision = resolveAISecurityPolicy({ element: input });
    const value = readValueForAI('secret-token', decision);

    expect(decision.canRead).toBe(true);
    expect(decision.readAccess).toBe('mask');
    expect(value).not.toBe('secret-token');
    expect(String(value)).toContain('***');
  });

  it('blocks actions when data-ai-act=off', () => {
    const button = document.createElement('button');
    button.setAttribute('data-ai-act', 'off');

    const result = evaluateAIActionSecurity({
      actionKind: 'ui_click',
      element: button,
    });

    expect(result.allowed).toBe(false);
    expect(result.reason).toBe('data_ai_act_off');
  });

  it('blocks submit when data-ai-submit=off', () => {
    const form = document.createElement('form');
    form.setAttribute('data-ai-submit', 'off');

    const result = evaluateAIActionSecurity({
      actionKind: 'ui_submit_form',
      element: form,
    });

    expect(result.allowed).toBe(false);
    expect(result.reason).toBe('data_ai_submit_off');
  });

  it('marks dangerous actions as confirmation-required by default', () => {
    const button = document.createElement('button');
    const result = evaluateAIActionSecurity({
      actionKind: 'delete_record',
      element: button,
    });

    expect(result.allowed).toBe(true);
    expect(result.requireConfirm).toBe(true);
  });
});

