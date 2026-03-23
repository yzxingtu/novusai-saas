import { describe, expect, it } from 'vitest';

import { transformMenuData } from '../menu-transformer';

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
});
