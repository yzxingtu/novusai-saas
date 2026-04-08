// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import { UIActionExecutor } from '../ui-action-executor';

describe('uiActionExecutor', () => {
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

