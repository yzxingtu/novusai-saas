// @vitest-environment happy-dom
/**
 * Test type: behavioral
 * Verifies: the shared panel utility actions expose text labels in the regular toolbar
 * while preserving icon-only compact rendering inside the editor-AI rail.
 * Mock strategy: ant-design wrappers and icons are stubbed, while the utility-action
 * rendering logic runs real.
 */
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatPanelUtilityActions from '../AIChatPanelUtilityActions.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Dropdown: defineComponent({
    name: 'DropdownStub',
    template: '<div><slot /><slot name="overlay" /></div>',
  }),
  Menu: defineComponent({
    name: 'MenuStub',
    props: {
      items: {
        default: () => [],
        type: Array,
      },
    },
    template: '<div class="menu-stub">{{ items.length }}</div>',
  }),
  Spin: defineComponent({
    name: 'SpinStub',
    template: '<span class="spin-stub"></span>',
  }),
  Tooltip: defineComponent({
    name: 'TooltipStub',
    template: '<div><slot /></div>',
  }),
}));

describe('AIChatPanelUtilityActions', () => {
  it('shows readable labels in the regular shared toolbar', () => {
    const wrapper = mount(AIChatPanelUtilityActions, {
      props: {
        compact: false,
        hasHeaderVariableValues: true,
        showHeaderMemoryButton: true,
        showHeaderMoreMenu: true,
        showHeaderVarsButton: true,
        showHistory: false,
        showMemoryPanel: false,
      },
    });

    expect(wrapper.text()).toContain('user.aiChat.varsModal.editVars');
    expect(wrapper.text()).toContain('common.aiPanel.newChat');
    expect(wrapper.text()).toContain('common.aiPanel.history');
    expect(wrapper.text()).toContain('common.aiPanel.memory');
    expect(wrapper.text()).toContain('common.aiPanel.moreActions');
  });

  it('keeps compact page-rail actions icon-first without text labels', () => {
    const wrapper = mount(AIChatPanelUtilityActions, {
      props: {
        compact: true,
        showHeaderMemoryButton: true,
        showHeaderMoreMenu: true,
        showHeaderVarsButton: true,
        showHistory: false,
        showMemoryPanel: false,
      },
    });

    expect(wrapper.text()).not.toContain('user.aiChat.varsModal.editVars');
    expect(wrapper.text()).not.toContain('common.aiPanel.newChat');
    expect(wrapper.text()).not.toContain('common.aiPanel.history');
    expect(wrapper.text()).not.toContain('common.aiPanel.memory');
    expect(wrapper.text()).not.toContain('common.aiPanel.moreActions');
    expect(wrapper.findAll('button')).toHaveLength(5);
  });
});
