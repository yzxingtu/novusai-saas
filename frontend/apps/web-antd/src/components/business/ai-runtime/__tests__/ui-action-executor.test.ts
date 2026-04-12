// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from 'vitest';

import * as securityPolicy from '../security-policy';
import { UIActionExecutor } from '../ui-action-executor';

describe('uiActionExecutor', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = '';
    document.body.removeAttribute('data-page-key');
    document.title = '';
  });

  it('executes ui_click and returns surface diff', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="open-drawer">Open Drawer</button>
    `;

    const trigger = document.querySelector(
      '[data-testid="open-drawer"]',
    ) as HTMLButtonElement;
    trigger.addEventListener('click', () => {
      if (document.querySelector('.ant-drawer')) {
        return;
      }
      const drawer = document.createElement('div');
      drawer.className = 'ant-drawer';
      drawer.innerHTML = `<div class="ant-drawer-title">Create Agent</div>`;
      document.body.appendChild(drawer);
    });

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:open-drawer',
      wait_timeout_ms: 20,
    });

    expect(result.success).toBe(true);
    expect(result.diff.changed).toBe(true);
    expect(result.diff.surfaces_added.some((item) => item.kind === 'drawer')).toBe(
      true,
    );
    expect(result.diff.ui_epoch).toBeGreaterThan(0);
    expect(result.diff.active_surface_id).toBeTruthy();
    expect(result.diff.page_key_changed).toBe(false);
  });

  it('returns unsupported action type error', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_hover' as never,
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('invalid_action_type');
    expect(result.diff.changed).toBe(false);
  });

  it('returns invalid_input when ui_click has no target_locator', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('invalid_input');
    expect(result.diff.changed).toBe(false);
  });

  it('returns not_found when locator cannot be resolved', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = '<button>Existing</button>';

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'text:missing-target',
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('not_found');
    expect(result.diff.changed).toBe(false);
  });

  it('returns ambiguous when locator resolves to multiple matches', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button>Duplicate Action</button>
      <a href="#a">Duplicate Action</a>
    `;

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'Duplicate Action',
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('ambiguous');
    expect(Array.isArray(result.data?.candidates)).toBe(true);
    expect((result.data?.candidates as unknown[]).length).toBeGreaterThan(1);
  });

  it('returns policy blocked when target is disallowed by policy', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="blocked-submit" data-ai-act="off">Submit</button>
    `;

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:blocked-submit',
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('data_ai_act_off');
    expect(result.diff.changed).toBe(false);
  });

  it('returns confirmation_required when security requires confirm', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="dangerous-action">Dangerous Action</button>
    `;

    vi.spyOn(securityPolicy, 'evaluateAIActionSecurity').mockReturnValue({
      actionKind: 'click',
      allowed: true,
      decision: {
        actAccess: 'allow',
        blockedReasons: [],
        canAct: true,
        canRead: true,
        canSubmit: true,
        readAccess: 'allow',
        requireConfirm: true,
        submitAccess: 'allow',
        visible: true,
      },
      requireConfirm: true,
    });

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:dangerous-action',
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('confirmation_required');
    expect(result.diff.changed).toBe(false);
  });

  it('tracks surfaces_removed in incremental diff', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="toggle-modal">Toggle Modal</button>
    `;
    const toggle = document.querySelector(
      '[data-testid="toggle-modal"]',
    ) as HTMLButtonElement;
    toggle.addEventListener('click', () => {
      const existing = document.querySelector('.ant-modal');
      if (existing) {
        existing.remove();
        return;
      }
      const modal = document.createElement('div');
      modal.className = 'ant-modal';
      modal.innerHTML = `<div class="ant-modal-title">Quick Start</div>`;
      document.body.appendChild(modal);
    });

    const executor = new UIActionExecutor();
    await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:toggle-modal',
      wait_timeout_ms: 20,
    });
    const second = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:toggle-modal',
      wait_timeout_ms: 20,
    });

    expect(second.success).toBe(true);
    expect(second.diff.changed).toBe(true);
    expect(second.diff.surfaces_removed.length).toBeGreaterThan(0);
  });

  it('executes ui_open_surface successfully for requested kind', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="open-surface">Open Surface</button>
    `;

    const trigger = document.querySelector(
      '[data-testid="open-surface"]',
    ) as HTMLButtonElement;
    trigger.addEventListener('click', () => {
      if (document.querySelector('.ant-drawer')) {
        return;
      }
      const drawer = document.createElement('div');
      drawer.className = 'ant-drawer';
      drawer.innerHTML = `<div class="ant-drawer-title">Agent Drawer</div>`;
      document.body.appendChild(drawer);
    });

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_open_surface',
      surface: {
        kind: 'drawer',
        locator: 'testid:open-surface',
      },
      wait_timeout_ms: 20,
    });

    expect(result.success).toBe(true);
    expect(result.diff.changed).toBe(true);
    expect(result.diff.surfaces_added.some((item) => item.kind === 'drawer')).toBe(
      true,
    );
  });

  it('returns surface_not_opened when requested surface kind does not match', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="open-drawer-only">Open Drawer</button>
    `;

    const trigger = document.querySelector(
      '[data-testid="open-drawer-only"]',
    ) as HTMLButtonElement;
    trigger.addEventListener('click', () => {
      const drawer = document.createElement('div');
      drawer.className = 'ant-drawer';
      drawer.innerHTML = `<div class="ant-drawer-title">Drawer Only</div>`;
      document.body.appendChild(drawer);
    });

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_open_surface',
      surface: {
        kind: 'modal',
        locator: 'testid:open-drawer-only',
      },
      wait_timeout_ms: 20,
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('surface_not_opened');
    expect(result.diff.surfaces_added.some((item) => item.kind === 'drawer')).toBe(
      true,
    );
  });

  it('returns invalid_input when ui_open_surface has no locator', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_open_surface',
      surface: { kind: 'drawer' },
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('invalid_input');
    expect(result.diff.changed).toBe(false);
  });

  it('keeps diff unchanged when semantic change is false and ui does not change', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="noop-click">Noop</button>
    `;

    const trigger = document.querySelector(
      '[data-testid="noop-click"]',
    ) as HTMLButtonElement;
    trigger.addEventListener('click', () => {
      // intentional noop
    });

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:noop-click',
    });

    expect(result.success).toBe(true);
    expect(result.diff.changed).toBe(false);
    expect(result.diff.page_key_changed).toBe(false);
    expect(result.diff.ui_epoch).toBe(0);
  });

  it('marks diff changed when page key changes even without new overlays', async () => {
    let currentPageKey = 'admin.ai.agents';
    document.body.innerHTML = `
      <button data-testid="change-page-key">Change</button>
    `;
    const trigger = document.querySelector(
      '[data-testid="change-page-key"]',
    ) as HTMLButtonElement;
    trigger.addEventListener('click', () => {
      currentPageKey = 'admin.ai.models';
    });

    const executor = new UIActionExecutor({
      getPageKey: () => currentPageKey,
    });
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:change-page-key',
    });

    expect(result.success).toBe(true);
    expect(result.diff.changed).toBe(true);
    expect(result.diff.page_key_changed).toBe(true);
  });

  it('clicks nested anchor inside pagination item', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <ul class="ant-pagination">
        <li class="ant-pagination-item" data-testid="page-item-2">
          <a href="#page-2">2</a>
        </li>
      </ul>
    `;

    let nestedAnchorClicked = 0;
    const anchor = document.querySelector(
      '[data-testid="page-item-2"] a',
    ) as HTMLAnchorElement;
    anchor.addEventListener('click', () => {
      nestedAnchorClicked += 1;
    });

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:page-item-2',
    });

    expect(result.success).toBe(true);
    expect(result.data?.target_kind).toBe('pagination');
    expect(result.diff.changed).toBe(true);
    expect(nestedAnchorClicked).toBe(1);
  });

  it('returns failure path when clicking disabled target', async () => {
    document.body.setAttribute('data-page-key', 'admin.ai.agents');
    document.body.innerHTML = `
      <button data-testid="disabled-submit" disabled>Submit</button>
    `;

    const executor = new UIActionExecutor();
    const result = await executor.execute({
      action_type: 'ui_click',
      target_locator: 'testid:disabled-submit',
      wait_timeout_ms: 20,
    });

    expect(result.success).toBe(false);
    expect(result.error_type).toBe('element_disabled');
    expect(result.diff.changed).toBe(false);
  });
});
