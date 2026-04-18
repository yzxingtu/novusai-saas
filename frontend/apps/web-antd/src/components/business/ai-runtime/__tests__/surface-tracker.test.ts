import { describe, expect, it } from 'vitest';

import { UISurfaceTracker } from '../surface-tracker';

describe('uISurfaceTracker', () => {
  it('sync tracks added/updated/removed and page metadata/route changes', () => {
    const tracker = new UISurfaceTracker();

    const first = tracker.sync({
      overlays: [
        {
          key: 'modal:editor',
          kind: 'modal',
          metadata: {
            step: 1,
          },
          title: '编辑弹窗',
        },
        {
          key: 'drawer:filters',
          kind: 'drawer',
          metadata: {
            pinned: true,
          },
          title: '筛选抽屉',
        },
      ],
      page: {
        key: 'page:agents',
        metadata: {
          version: 1,
        },
        pageKey: 'agents',
        routePath: '/admin/ai/agents',
        title: '智能体',
      },
    });

    expect(first.changed).toBe(true);
    expect(first.added.map((surface) => surface.key)).toEqual([
      'page:agents',
      'modal:editor',
      'drawer:filters',
    ]);
    expect(first.updated).toHaveLength(0);
    expect(first.removed).toHaveLength(0);
    expect(tracker.getStack().map((surface) => surface.key)).toEqual([
      'page:agents',
      'modal:editor',
      'drawer:filters',
    ]);

    const stable = tracker.sync({
      overlays: [
        {
          key: 'modal:editor',
          kind: 'modal',
          metadata: {
            step: 1,
          },
          title: '编辑弹窗',
        },
        {
          key: 'drawer:filters',
          kind: 'drawer',
          metadata: {
            pinned: true,
          },
          title: '筛选抽屉',
        },
      ],
      page: {
        key: 'page:agents',
        metadata: {
          version: 1,
        },
        pageKey: 'agents',
        routePath: '/admin/ai/agents',
        title: '智能体',
      },
    });

    expect(stable.changed).toBe(false);
    expect(stable.added).toHaveLength(0);
    expect(stable.updated).toHaveLength(0);
    expect(stable.removed).toHaveLength(0);

    const changed = tracker.sync({
      overlays: [
        {
          key: 'modal:editor',
          kind: 'modal',
          metadata: {
            step: 2,
          },
          title: '编辑弹窗(新版)',
        },
      ],
      page: {
        key: 'page:agents',
        metadata: {
          version: 2,
        },
        pageKey: 'agents-v2',
        routePath: '/admin/ai/agents?tab=all',
        title: '智能体列表',
      },
    });

    expect(changed.changed).toBe(true);
    expect(changed.added).toHaveLength(0);
    expect(changed.removed.map((surface) => surface.key)).toEqual([
      'drawer:filters',
    ]);
    expect(changed.updated.map((surface) => surface.key).toSorted()).toEqual([
      'modal:editor',
      'page:agents',
    ]);
    expect(tracker.getStack().map((surface) => surface.key)).toEqual([
      'page:agents',
      'modal:editor',
    ]);
    expect(tracker.getActiveSurface()?.key).toBe('modal:editor');

    const pageSurface = tracker.getStack()[0];
    expect(pageSurface?.pageKey).toBe('agents-v2');
    expect(pageSurface?.routePath).toBe('/admin/ai/agents?tab=all');
    expect(pageSurface?.metadata).toEqual({
      version: 2,
    });

    const active = tracker.getActiveSurface();
    expect(active?.title).toBe('编辑弹窗(新版)');
    if (!active) {
      throw new Error('expected active surface');
    }
    active.title = 'mutated outside';
    expect(tracker.getActiveSurface()?.title).toBe('编辑弹窗(新版)');
  });

  it('openOverlay updates stack and closeSurfaceById cascades children', () => {
    const tracker = new UISurfaceTracker();

    tracker.sync({
      overlays: [],
      page: {
        key: 'page:home',
        pageKey: 'home',
        routePath: '/admin/home',
        title: '首页',
      },
    });

    const parent = tracker.openOverlay({
      key: 'modal:parent',
      kind: 'modal',
      title: '父弹窗',
    });
    tracker.openOverlay({
      key: 'popover:child',
      kind: 'popover',
      parentKey: 'modal:parent',
      title: '子气泡',
    });
    tracker.openOverlay({
      key: 'dropdown:grandchild',
      kind: 'dropdown',
      parentKey: 'popover:child',
      title: '孙级菜单',
    });
    tracker.openOverlay({
      key: 'drawer:side',
      kind: 'drawer',
      title: '侧栏抽屉',
    });

    const reopenedParent = tracker.openOverlay({
      key: 'modal:parent',
      kind: 'modal',
      title: '父弹窗(置顶)',
    });

    expect(reopenedParent.id).toBe(parent.id);
    expect(tracker.getActiveSurface()?.key).toBe('modal:parent');
    expect(tracker.getStack().map((surface) => surface.key)).toEqual([
      'page:home',
      'popover:child',
      'dropdown:grandchild',
      'drawer:side',
      'modal:parent',
    ]);

    const removed = tracker.closeSurfaceById(parent.id);
    expect(removed.map((surface) => surface.key).toSorted()).toEqual([
      'dropdown:grandchild',
      'modal:parent',
      'popover:child',
    ]);
    expect(tracker.getStack().map((surface) => surface.key)).toEqual([
      'page:home',
      'drawer:side',
    ]);
    expect(tracker.getActiveSurface()?.key).toBe('drawer:side');
    expect(tracker.closeSurfaceById('surface:unknown:999')).toEqual([]);
  });
});
