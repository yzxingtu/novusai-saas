import { describe, expect, it } from 'vitest';

import {
  buildMenuNavigationEntries,
  resolveMenuNavigationTarget,
  searchMenuNavigationEntries,
} from '../menu-navigation';

describe('menu-navigation', () => {
  it('matches semantic navigation from backend-provided ai metadata', () => {
    const entries = buildMenuNavigationEntries({
      currentEndpoint: 'admin',
      menus: [
        {
          name: '智能体管理',
          path: '/admin/ai/agents',
          meta: {
            ai: {
              category: 'ai',
              description: '创建、编辑和管理 AI 智能体',
              keywords: ['智能体', 'AI助手', 'assistant'],
              capabilities: ['create_agent', 'edit_agent'],
            },
          },
        },
      ] as any,
    });

    const matches = searchMenuNavigationEntries(entries, '帮我新增 AI 助手');

    expect(matches).toHaveLength(1);
    expect(matches[0]?.pageKey).toBe('admin.ai.agents');
    expect(matches[0]?.score).toBeGreaterThanOrEqual(900);
  });

  it('resolves by exact title without local preset knowledge', () => {
    const entries = buildMenuNavigationEntries({
      currentEndpoint: 'admin',
      menus: [
        {
          name: '插件管理',
          path: '/admin/plugins',
        },
      ] as any,
    });

    const resolution = resolveMenuNavigationTarget({
      currentPageKey: 'admin.dashboard',
      currentPath: '/admin/dashboard',
      entries,
      target: '打开插件管理',
    });

    expect(resolution.kind).toBe('success');
    if (resolution.kind === 'success') {
      expect(resolution.entry.path).toBe('/admin/plugins');
    }
  });

  it('serializes compact navigation catalog without runtime context fields', () => {
    const entries = buildMenuNavigationEntries({
      currentEndpoint: 'admin',
      menus: [
        {
          name: '智能体管理',
          path: '/admin/ai/agents',
        },
      ] as any,
    });

    expect(entries[0]).toMatchObject({
      breadcrumb: ['智能体管理'],
      endpoint: 'admin',
      pageKey: 'admin.ai.agents',
      path: '/admin/ai/agents',
    });

    expect(Object.keys(entries[0] ?? {}).sort()).toEqual([
      'breadcrumb',
      'capabilities',
      'category',
      'description',
      'endpoint',
      'icon',
      'key',
      'keywords',
      'pageKey',
      'path',
      'title',
    ]);
  });
});
