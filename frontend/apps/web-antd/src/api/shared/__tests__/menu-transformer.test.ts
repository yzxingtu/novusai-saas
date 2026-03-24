import { describe, expect, it } from 'vitest';

import {
  extractPermissionsFromMenus,
  transformMenuData,
} from '../menu-transformer';

describe('menu-transformer', () => {
  it('does not resolve plugin standalone page menus as host view components', () => {
    const [menu] = transformMenuData(
      [
        {
          code: 'menu:admin.plugin_novusdoc_novusdoc_admin',
          component: 'NovusDocPage',
          name: '文档管理',
          path: '/admin/plugins/novusdoc',
        },
      ],
      'admin',
    );

    expect(menu?.path).toBe('/admin/plugins/novusdoc');
    expect(menu?.component).toBeUndefined();
  });

  it('includes menu code in extracted permissions for plugin route access', () => {
    const permissions = extractPermissionsFromMenus([
      {
        code: 'menu:tenant.plugin_storage_billing_storage-billing-home',
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
});
