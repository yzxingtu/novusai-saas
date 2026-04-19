// @vitest-environment happy-dom
import { describe, expect, it } from 'vitest';

import {
  evaluateAIActionSecurity,
  readValueForAI,
  resolveAISecurityPolicy,
} from '../security-policy';

describe('security-policy enforcement', () => {
  it('hides and blocks nodes marked with data-ai=off', () => {
    const region = document.createElement('div');
    region.dataset.ai = 'off';

    const decision = resolveAISecurityPolicy({
      element: region,
      actionKind: 'ui_click',
    });
    const action = evaluateAIActionSecurity({
      element: region,
      actionKind: 'ui_click',
    });

    expect(decision.visible).toBe(false);
    expect(decision.canRead).toBe(false);
    expect(action.allowed).toBe(false);
    expect(action.reason).toBe('data_ai_off');
  });

  it('hides and blocks nodes marked with data-ai-disabled', () => {
    const region = document.createElement('div');
    region.dataset.aiDisabled = '';

    const decision = resolveAISecurityPolicy({
      element: region,
      actionKind: 'ui_click',
    });
    const action = evaluateAIActionSecurity({
      element: region,
      actionKind: 'ui_click',
    });

    expect(decision.visible).toBe(false);
    expect(decision.canRead).toBe(false);
    expect(action.allowed).toBe(false);
    expect(action.reason).toBe('data_ai_disabled');
  });

  it('treats password/token/captcha/file fields as unreadable by default', () => {
    const passwordInput = document.createElement('input');
    passwordInput.setAttribute('type', 'password');

    const tokenInput = document.createElement('input');
    tokenInput.setAttribute('name', 'api_token');

    const captchaInput = document.createElement('input');
    captchaInput.setAttribute('name', 'captcha_code');

    const fileInput = document.createElement('input');
    fileInput.setAttribute('type', 'file');

    const passwordPolicy = resolveAISecurityPolicy({ element: passwordInput });
    const tokenPolicy = resolveAISecurityPolicy({ element: tokenInput });
    const captchaPolicy = resolveAISecurityPolicy({ element: captchaInput });
    const filePolicy = resolveAISecurityPolicy({ element: fileInput });

    expect(passwordPolicy.canRead).toBe(false);
    expect(passwordPolicy.sensitiveFieldCategory).toBe('password');
    expect(tokenPolicy.canRead).toBe(false);
    expect(tokenPolicy.sensitiveFieldCategory).toBe('token');
    expect(captchaPolicy.canRead).toBe(false);
    expect(captchaPolicy.sensitiveFieldCategory).toBe('captcha');
    expect(filePolicy.canRead).toBe(false);
    expect(filePolicy.sensitiveFieldCategory).toBe('file_upload');
    expect(readValueForAI('abc', tokenPolicy)).toBeUndefined();
  });

  it('enforces submit-off from route policy bridge', () => {
    const form = document.createElement('form');

    const action = evaluateAIActionSecurity({
      actionKind: 'ui_submit_form',
      element: form,
      routePolicy: {
        enabled: true,
        submit: 'off',
      },
    });

    expect(action.allowed).toBe(false);
    expect(action.reason).toBe('route_submit_off');
  });
});
