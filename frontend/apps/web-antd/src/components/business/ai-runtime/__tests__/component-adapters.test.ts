// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from 'vitest';

import {
  ANTD_BUTTON_ADAPTER_ID,
  ANTD_DRAWER_ADAPTER_ID,
  ANTD_MENU_ADAPTER_ID,
  ANTD_MODAL_ADAPTER_ID,
  ANTD_TABS_ADAPTER_ID,
  createAntdButtonAdapter,
  createAntdDrawerAdapter,
  createAntdMenuAdapter,
  createAntdModalAdapter,
  createAntdTabsAdapter,
  createDefaultComponentAdapters,
  DEFAULT_COMPONENT_ADAPTER_PRIORITIES,
  VUE_ROUTER_ADAPTER_ID,
} from '../component-adapters';
import { tAiRuntime } from '../i18n';
import type { UIAdapterContext } from '../types';

function createAdapterContext(
  root: ParentNode = document.body,
): UIAdapterContext {
  return {
    activeSurfaceId: null,
    document,
    mode: 'compact',
    now: Date.now(),
    root,
    route: null,
  };
}

describe('component adapters', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('creates default adapters in fixed order with expected priorities', () => {
    const adapters = createDefaultComponentAdapters({
      router: {
        getRoute: () => ({
          fullPath: '/admin/system/logs',
          meta: {
            title: '系统日志',
          },
          name: 'system-logs',
        }),
      },
    });

    expect(adapters.map((adapter) => adapter.id)).toEqual([
      VUE_ROUTER_ADAPTER_ID,
      ANTD_MODAL_ADAPTER_ID,
      ANTD_DRAWER_ADAPTER_ID,
      ANTD_MENU_ADAPTER_ID,
      ANTD_TABS_ADAPTER_ID,
      ANTD_BUTTON_ADAPTER_ID,
    ]);

    expect(adapters.map((adapter) => adapter.priority)).toEqual([
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[VUE_ROUTER_ADAPTER_ID],
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_MODAL_ADAPTER_ID],
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_DRAWER_ADAPTER_ID],
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_MENU_ADAPTER_ID],
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_TABS_ADAPTER_ID],
      DEFAULT_COMPONENT_ADAPTER_PRIORITIES[ANTD_BUTTON_ADAPTER_ID],
    ]);

    const page = adapters[0]?.collect(createAdapterContext()).page;
    expect(page).toMatchObject({
      key: 'page:system-logs',
      pageKey: 'system-logs',
      routePath: '/admin/system/logs',
      title: '系统日志',
    });
  });

  it('collects button nodes, skips hidden elements, de-duplicates and keeps disabled metadata', () => {
    document.body.innerHTML = `
      <section>
        <button class="ant-btn ant-btn-primary" data-testid="save-btn" disabled>保存</button>
        <button class="ant-btn" data-testid="hidden-btn" hidden>隐藏</button>
        <div class="ant-btn" role="button" data-testid="save-btn">重复保存</div>
        <button class="ant-btn" data-testid="cancel-btn" aria-disabled="true">取消</button>
      </section>
    `;

    const result = createAntdButtonAdapter(88).collect(createAdapterContext());
    const nodes = result.nodes ?? [];

    expect(nodes).toHaveLength(2);
    expect(nodes.map((node) => node.locator)).toEqual([
      '[data-testid="save-btn"]',
      '[data-testid="cancel-btn"]',
    ]);

    expect(nodes[0]).toMatchObject({
      adapterId: ANTD_BUTTON_ADAPTER_ID,
      disabled: true,
      kind: 'button',
      label: '保存',
      locator: '[data-testid="save-btn"]',
      priority: 88,
      source: 'adapter',
      visible: true,
    });
    expect(nodes[0]?.metadata).toMatchObject({
      className: expect.stringContaining('ant-btn'),
      tag: 'button',
    });

    expect(nodes[1]).toMatchObject({
      disabled: true,
      label: '取消',
      locator: '[data-testid="cancel-btn"]',
    });
  });

  it('collects menu nodes, skips hidden entries, de-duplicates and marks selected/disabled', () => {
    document.body.innerHTML = `
      <ul class="ant-menu">
        <li class="ant-menu-item ant-menu-item-selected" data-testid="menu-users">用户管理</li>
        <li class="ant-menu-item" data-testid="menu-settings" aria-disabled="true">系统设置</li>
        <li class="ant-menu-item" data-testid="menu-hidden" style="display:none">隐藏菜单</li>
        <div role="menuitem" data-testid="menu-users">重复用户管理</div>
      </ul>
    `;

    const result = createAntdMenuAdapter(77).collect(createAdapterContext());
    const nodes = result.nodes ?? [];

    expect(nodes).toHaveLength(2);
    expect(nodes.map((node) => node.locator)).toEqual([
      '[data-testid="menu-users"]',
      '[data-testid="menu-settings"]',
    ]);

    const usersNode = nodes.find(
      (node) => node.locator === '[data-testid="menu-users"]',
    );
    const settingsNode = nodes.find(
      (node) => node.locator === '[data-testid="menu-settings"]',
    );

    expect(usersNode).toMatchObject({
      adapterId: ANTD_MENU_ADAPTER_ID,
      disabled: false,
      kind: 'menu-item',
      priority: 77,
    });
    expect(usersNode?.metadata).toEqual({
      selected: true,
    });

    expect(settingsNode).toMatchObject({
      disabled: true,
    });
    expect(settingsNode?.metadata).toEqual({
      selected: false,
    });
  });

  it('collects tab nodes, skips hidden entries, de-duplicates and marks active/disabled', () => {
    document.body.innerHTML = `
      <section>
        <div class="ant-tabs-tab ant-tabs-tab-active" data-testid="tab-overview">概览</div>
        <div class="ant-tabs-tab" data-testid="tab-overview">重复概览</div>
        <div class="ant-tabs-tab" data-testid="tab-settings" aria-disabled="true">设置</div>
        <div class="ant-tabs-tab ant-tabs-tab-active" data-testid="tab-hidden" aria-hidden="true">隐藏标签</div>
      </section>
    `;

    const result = createAntdTabsAdapter(66).collect(createAdapterContext());
    const nodes = result.nodes ?? [];

    expect(nodes).toHaveLength(2);
    expect(nodes.map((node) => node.locator)).toEqual([
      '[data-testid="tab-overview"]',
      '[data-testid="tab-settings"]',
    ]);

    const overviewNode = nodes.find(
      (node) => node.locator === '[data-testid="tab-overview"]',
    );
    const settingsNode = nodes.find(
      (node) => node.locator === '[data-testid="tab-settings"]',
    );

    expect(overviewNode).toMatchObject({
      adapterId: ANTD_TABS_ADAPTER_ID,
      disabled: false,
      kind: 'tab',
      priority: 66,
    });
    expect(overviewNode?.metadata).toEqual({
      active: true,
    });

    expect(settingsNode).toMatchObject({
      disabled: true,
    });
    expect(settingsNode?.metadata).toEqual({
      active: false,
    });
  });

  it('collects modal overlays with title fallback, key generation and hidden filtering', () => {
    document.body.innerHTML = `
      <div class="ant-modal-root">
        <div class="ant-modal-wrap" data-ai-surface-id="main-modal">
          <div class="ant-modal-title">  主弹窗   标题  </div>
        </div>
      </div>
      <div class="ant-modal" data-testid="modal-testid"></div>
      <div class="ant-modal" id="modal-id">
        <div class="ant-modal-title">   </div>
      </div>
      <div class="ant-modal" data-testid="modal-hidden" style="display:none"></div>
      <div class="ant-modal"></div>
    `;

    const result = createAntdModalAdapter(80).collect(createAdapterContext());
    const overlays = result.overlays ?? [];
    const fallbackTitle = tAiRuntime('surfaceTitle.modal', { index: 1 });

    expect(overlays).toHaveLength(4);
    expect(overlays.map((overlay) => overlay.key)).toEqual([
      'modal:main-modal',
      'modal:modal-testid',
      'modal:modal-id',
      'modal:antd:4',
    ]);

    expect(overlays[0]).toMatchObject({
      kind: 'modal',
      title: '主弹窗 标题',
    });
    expect(overlays[0]?.metadata).toEqual({
      adapter: ANTD_MODAL_ADAPTER_ID,
    });

    expect(overlays[1]?.title).toBe(fallbackTitle);
    expect(overlays[2]?.title).toBe(fallbackTitle);
    expect(overlays[3]?.title).toBe(fallbackTitle);
  });

  it('collects drawer overlays with title fallback, key generation and hidden filtering', () => {
    document.body.innerHTML = `
      <div class="ant-drawer-content-wrapper" data-ai-surface-id="main-drawer">
        <div class="ant-drawer-title">  主抽屉   标题  </div>
      </div>
      <div class="ant-drawer-content" data-testid="drawer-testid"></div>
      <div class="ant-drawer-content" id="drawer-id">
        <div class="ant-drawer-title">   </div>
      </div>
      <div class="ant-drawer-content-wrapper" data-testid="drawer-hidden" style="visibility:hidden"></div>
      <div class="ant-drawer-content"></div>
    `;

    const result = createAntdDrawerAdapter(75).collect(createAdapterContext());
    const overlays = result.overlays ?? [];
    const fallbackTitle = tAiRuntime('surfaceTitle.drawer', { index: 1 });

    expect(overlays).toHaveLength(4);
    expect(overlays.map((overlay) => overlay.key)).toEqual([
      'drawer:main-drawer',
      'drawer:drawer-testid',
      'drawer:drawer-id',
      'drawer:antd:4',
    ]);

    expect(overlays[0]).toMatchObject({
      kind: 'drawer',
      title: '主抽屉 标题',
    });
    expect(overlays[0]?.metadata).toEqual({
      adapter: ANTD_DRAWER_ADAPTER_ID,
    });

    expect(overlays[1]?.title).toBe(fallbackTitle);
    expect(overlays[2]?.title).toBe(fallbackTitle);
    expect(overlays[3]?.title).toBe(fallbackTitle);
  });
});
