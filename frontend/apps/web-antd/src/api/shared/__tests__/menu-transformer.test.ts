import { describe, expect, it } from 'vitest';

import {
  extractPermissionsFromMenus,
  needsTransform,
  setExistingComponents,
  transformMenuData,
} from '../menu-transformer';

describe('menu-transformer', () => {
  it('maps the current backend MenuResponse contract into route meta', () => {
    setExistingComponents({
      '../views/admin/system/users/index.vue': {},
    });

    const [menu] = transformMenuData(
      [
        {
          code: 'menu:admin.system.users',
          component: 'system/users/index',
          hidden: true,
          icon: 'lucide:users',
          id: 1,
          meta: {
            ai: {
              capabilities: ['read'],
              category: 'system',
              description: 'Manage users',
              keywords: ['users'],
              mode: 'guide',
            },
          },
          name: '用户管理',
          path: '/system/users',
          sort_order: 20,
        },
      ],
      'admin',
    );

    expect(menu).toMatchObject({
      component: '/admin/system/users/index.vue',
      meta: {
        ai: {
          capabilities: ['read'],
          category: 'system',
          description: 'Manage users',
          keywords: ['users'],
          mode: 'guide',
        },
        hideInMenu: true,
        icon: 'lucide:users',
        order: 20,
        title: '用户管理',
        accessCodes: ['menu:admin.system.users'],
      },
      name: 'menu:admin.system.users',
      path: '/admin/system/users',
    });
  });

  it('uses the backend plugin menu component contract directly', () => {
    const [menu] = transformMenuData(
      [
        {
          code: 'menu:admin.plugin_novusdoc_novusdoc_admin',
          component: null,
          id: 1,
          name: '文档管理',
          path: '/admin/plugins/novusdoc',
        },
      ],
      'admin',
    );

    expect(menu?.path).toBe('/admin/plugins/novusdoc');
    expect(menu?.component).toBeUndefined();
  });

  it('always transforms non-empty backend menu arrays through the current contract', () => {
    expect(
      needsTransform([
        {
          code: 'menu:admin.system.roles',
          component: 'system/roles/index',
          id: 2,
          name: '角色管理',
          path: '/system/roles',
        },
      ]),
    ).toBe(true);
    expect(needsTransform([])).toBe(false);
  });

  it('includes menu code in extracted permissions for plugin route access', () => {
    const permissions = extractPermissionsFromMenus([
      {
        code: 'menu:tenant.plugin_storage_billing_storage-billing-home',
        id: 1,
        name: '模板管理',
        path: '/tenant/plugins/storage-billing',
        permissions: ['plugin.storage-billing.billing_portal:view'],
      },
    ]);

    expect(permissions).toContain(
      'menu:tenant.plugin_storage_billing_storage-billing-home',
    );
    expect(permissions).toContain('plugin.storage-billing.billing_portal:view');
  });

  it('writes menu code and backend permissions into route meta accessCodes', () => {
    setExistingComponents({
      '../views/tenant/ai/chat/index.vue': {},
    });

    const [menu] = transformMenuData(
      [
        {
          code: ' menu:tenant.ai.chat ',
          component: 'ai/chat/index',
          id: 1,
          name: 'AI Chat',
          path: '/ai/chat',
          permissions: [
            'agent_chat:chat',
            ' agent_chat:conversations ',
            'agent_chat:chat',
          ],
        },
      ],
      'tenant',
    );

    expect(menu?.meta?.accessCodes).toEqual([
      'menu:tenant.ai.chat',
      'agent_chat:chat',
      'agent_chat:conversations',
    ]);
  });
});
