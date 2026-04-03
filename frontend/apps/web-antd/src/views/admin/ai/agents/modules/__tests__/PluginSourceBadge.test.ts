import { mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';

import PluginSourceBadge from '../PluginSourceBadge.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => {
    switch (key) {
      case 'admin.ai.skillPackage.sourcePlugin': {
        return '插件';
      }
      case 'admin.ai.agent.sourcePluginDisabled': {
        return '来源插件已停用';
      }
      default: {
        return key;
      }
    }
  },
}));

const tagStub = {
  template: '<span><slot /></span>',
};

describe('PluginSourceBadge', () => {
  it('renders plugin display name when source plugin exists', () => {
    const wrapper = mount(PluginSourceBadge, {
      props: {
        sourcePlugin: 'novusdoc',
        sourcePluginDisplayName: '文档管理',
      },
      global: {
        stubs: {
          Tag: tagStub,
        },
      },
    });

    expect(wrapper.text()).toContain('插件 · 文档管理');
  });

  it('shows disabled state when source plugin is disabled', () => {
    const wrapper = mount(PluginSourceBadge, {
      props: {
        sourcePlugin: 'novusdoc',
        sourcePluginDisplayName: '文档管理',
        sourcePluginEnabled: false,
      },
      global: {
        stubs: {
          Tag: tagStub,
        },
      },
    });

    expect(wrapper.text()).toContain('来源插件已停用');
  });
});
