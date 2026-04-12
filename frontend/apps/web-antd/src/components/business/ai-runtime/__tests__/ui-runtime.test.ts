// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest';

import { UIGraphBuilder } from '../ui-graph-builder';
import { UISurfaceTracker } from '../surface-tracker';
import { createUIRuntime } from '../ui-runtime';
import type { UIComponentAdapter } from '../types';

function createStaticAdapter(options: {
  id: string;
  locator: string;
  priority: number;
  label: string;
}): UIComponentAdapter {
  return {
    id: options.id,
    priority: options.priority,
    collect() {
      return {
        nodes: [
          {
            adapterId: options.id,
            disabled: false,
            id: `${options.id}:${options.locator}`,
            kind: 'button',
            label: options.label,
            locator: options.locator,
            priority: options.priority,
            source: 'adapter',
            visible: true,
          },
        ],
      };
    },
  };
}

describe('ui-runtime phase-1 infrastructure', () => {
  it('uses adapter fast path first and falls back to DOM scanner when needed', () => {
    document.body.innerHTML = `
      <button class="ant-btn" data-testid="dom-save">保存</button>
    `;

    const adapterBuilder = new UIGraphBuilder({
      adapters: [
        createStaticAdapter({
          id: 'static-button',
          label: 'Adapter Save',
          locator: '[data-ai-id="adapter-save"]',
          priority: 60,
        }),
      ],
      includeDomFallbackInCompact: false,
    });

    const adapterGraph = adapterBuilder.build({
      mode: 'compact',
      route: {
        fullPath: '/admin/ai/agents',
        meta: {
          title: 'Agent',
        },
        name: 'agent',
      },
    });
    expect(adapterGraph.graph.nodes).toHaveLength(1);
    expect(adapterGraph.graph.nodes[0]?.label).toBe('Adapter Save');
    expect(adapterGraph.graph.stats.usedDomFallback).toBe(false);

    const fallbackBuilder = new UIGraphBuilder({
      adapters: [],
      includeDomFallbackInCompact: false,
    });
    const fallbackGraph = fallbackBuilder.build({
      mode: 'compact',
    });
    expect(fallbackGraph.graph.nodes.some((node) => node.locator.includes('dom-save'))).toBe(
      true,
    );
    expect(fallbackGraph.graph.stats.usedDomFallback).toBe(true);
  });

  it('tracks surface stack and supports page/drawer/modal/dropdown/popover sync', () => {
    const tracker = new UISurfaceTracker();
    const first = tracker.sync({
      overlays: [
        {
          key: 'drawer:editor',
          kind: 'drawer',
          title: '编辑抽屉',
        },
        {
          key: 'modal:confirm',
          kind: 'modal',
          title: '确认弹窗',
        },
      ],
      page: {
        key: 'page:agents',
        pageKey: 'agents',
        routePath: '/admin/ai/agents',
        title: '智能体',
      },
    });
    expect(first.changed).toBe(true);
    expect(tracker.getStack().map((surface) => surface.kind)).toEqual([
      'page',
      'drawer',
      'modal',
    ]);

    const second = tracker.sync({
      overlays: [
        {
          key: 'modal:confirm',
          kind: 'modal',
          title: '确认弹窗',
        },
        {
          key: 'dropdown:batch',
          kind: 'dropdown',
          title: '批量菜单',
        },
        {
          key: 'popover:hint',
          kind: 'popover',
          title: '提示气泡',
        },
      ],
      page: {
        key: 'page:agents',
        pageKey: 'agents',
        routePath: '/admin/ai/agents',
        title: '智能体',
      },
    });

    expect(second.removed.some((surface) => surface.kind === 'drawer')).toBe(true);
    expect(tracker.getStack().map((surface) => surface.kind)).toEqual([
      'page',
      'modal',
      'dropdown',
      'popover',
    ]);
    expect(tracker.getActiveSurface()?.kind).toBe('popover');
  });

  it('increments ui_epoch on graph/surface/route updates', () => {
    let route = {
      fullPath: '/admin/system/logs',
      meta: {
        title: '系统日志',
      },
      name: 'system-logs',
    };
    const runtime = createUIRuntime({
      adapters: [
        createStaticAdapter({
          id: 'runtime-adapter',
          label: 'Search',
          locator: '[data-ai-id="search"]',
          priority: 60,
        }),
      ],
      getRoute: () => route,
      route,
    });

    const initialized = runtime.initialize();
    expect(initialized.ui_graph.nodes.length).toBeGreaterThan(0);
    const epochAfterInit = initialized.ui_epoch;

    const opened = runtime.openSurface({
      key: 'modal:create',
      kind: 'modal',
      title: '新建弹窗',
    });
    expect(opened.ui_epoch).toBeGreaterThan(epochAfterInit);
    const epochAfterOpen = opened.ui_epoch;

    route = {
      fullPath: '/admin/system/configs',
      meta: {
        title: '系统配置',
      },
      name: 'system-configs',
    };
    const rebuilt = runtime.rebuildGraph({ mode: 'compact' });
    expect(rebuilt.ui_epoch).toBeGreaterThan(epochAfterOpen);
  });

  it('registers adapters by priority and keeps the higher-priority node', () => {
    const builder = new UIGraphBuilder({
      adapters: [],
    });
    const low = createStaticAdapter({
      id: 'low-priority',
      label: 'Low',
      locator: '[data-ai-id="shared"]',
      priority: 10,
    });
    const high = createStaticAdapter({
      id: 'high-priority',
      label: 'High',
      locator: '[data-ai-id="shared"]',
      priority: 99,
    });

    builder.registerAdapter(low);
    builder.registerAdapter(high);

    expect(builder.getAdapters().map((adapter) => adapter.id)).toEqual([
      'high-priority',
      'low-priority',
    ]);

    const graph = builder.build({
      mode: 'compact',
    });
    expect(graph.graph.nodes).toHaveLength(1);
    expect(graph.graph.nodes[0]?.label).toBe('High');
  });

  it('binds page surface_id for page nodes in compact snapshot', () => {
    document.body.innerHTML = `
      <button id="page-action">Page Action</button>
    `;

    const runtime = createUIRuntime({
      adapters: [],
      includeDomFallbackInCompact: false,
      route: {
        fullPath: '/admin/runtime/page-surface',
        meta: { title: 'Page Surface' },
        name: 'page-surface',
      },
    });
    const snapshot = runtime.initialize();
    const pageSurface = snapshot.surface_stack.find((surface) => surface.kind === 'page');
    expect(pageSurface).toBeTruthy();

    const pageNode = snapshot.ui_graph.nodes.find((node) => node.locator.includes('#page-action'));
    expect(pageNode).toBeTruthy();
    expect(pageNode?.surfaceId).toBe(pageSurface?.id);

    const scopedPageNodes = snapshot.ui_graph.nodes.filter(
      (node) => node.surfaceId === pageSurface?.id,
    );
    expect(scopedPageNodes.length).toBeGreaterThan(0);
  });

  it('binds page surface_id for adapter nodes when compact mode uses surfaces-only fallback', () => {
    document.body.innerHTML = `
      <button data-testid="adapter-page-action">Adapter Page Action</button>
    `;

    const runtime = createUIRuntime({
      adapters: [
        createStaticAdapter({
          id: 'adapter-page-node',
          label: 'Adapter Page Action',
          locator: 'testid:adapter-page-action',
          priority: 80,
        }),
      ],
      includeDomFallbackInCompact: false,
      route: {
        fullPath: '/admin/runtime/adapter-page-surface',
        meta: { title: 'Adapter Page Surface' },
        name: 'adapter-page-surface',
      },
    });

    const snapshot = runtime.initialize();
    const pageSurface = snapshot.surface_stack.find((surface) => surface.kind === 'page');
    expect(pageSurface).toBeTruthy();
    const adapterNode = snapshot.ui_graph.nodes.find(
      (node) => node.locator === 'testid:adapter-page-action',
    );
    expect(adapterNode).toBeTruthy();
    expect(adapterNode?.surfaceId).toBe(pageSurface?.id);
    expect(snapshot.ui_graph.stats.usedDomFallback).toBe(false);
  });

  it('excludes adapter nodes inside data-ai=off regions in graph binding', () => {
    document.body.innerHTML = `
      <div data-ai=" off ">
        <button data-testid="off-action">Off Action</button>
      </div>
      <button data-testid="safe-action">Safe Action</button>
    `;

    const runtime = createUIRuntime({
      adapters: [
        createStaticAdapter({
          id: 'adapter-off-node',
          label: 'Off Action',
          locator: 'text:Off Action',
          priority: 90,
        }),
        createStaticAdapter({
          id: 'adapter-safe-node',
          label: 'Safe Action',
          locator: 'testid:safe-action',
          priority: 80,
        }),
      ],
      includeDomFallbackInCompact: false,
    });

    const snapshot = runtime.initialize();
    const locators = snapshot.ui_graph.nodes.map((node) => node.locator);
    expect(locators).toContain('testid:safe-action');
    expect(locators).not.toContain('text:Off Action');
  });

  it('excludes data-ai=off and data-ai-panel regions from runtime graph', () => {
    document.body.innerHTML = `
      <div data-ai="off">
        <button id="off-action">Off Action</button>
      </div>
      <div data-ai-panel>
        <button id="panel-action">Panel Action</button>
      </div>
      <button id="safe-action">Safe Action</button>
    `;

    const runtime = createUIRuntime({
      adapters: [],
      includeDomFallbackInCompact: false,
    });
    const snapshot = runtime.initialize();
    const locators = snapshot.ui_graph.nodes.map((node) => node.locator);

    expect(locators.some((locator) => locator.includes('#safe-action'))).toBe(true);
    expect(locators.some((locator) => locator.includes('#off-action'))).toBe(false);
    expect(locators.some((locator) => locator.includes('#panel-action'))).toBe(false);
  });
});
