// @vitest-environment happy-dom
// Test type: behavioral
// Verifies: the slide-panel header keeps a stable panel title while route context stays secondary, and the compact utility actions emit in the intended order.
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatPanelHeader from '../AIChatPanelHeader.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    props: {
      icon: { type: String, required: false, default: '' },
    },
    template: '<span class="iconify-stub" :data-icon="icon"></span>',
  }),
}));

vi.mock('ant-design-vue', () => ({
  Tooltip: defineComponent({
    name: 'TooltipStub',
    template: '<div><slot /></div>',
  }),
}));

describe('AIChatPanelHeader', () => {
  it('keeps the panel title visible while route context stays secondary', () => {
    const wrapper = mount(AIChatPanelHeader, {
      props: {
        docked: true,
        headerConversationSummary: '2 common.globalAiChat.messages',
        panelTitle: 'common.aiPanel.title',
        routeNotice: 'common.aiPanel.routedTo Agent',
      },
    });

    expect(wrapper.text()).toContain('common.aiPanel.title');
    expect(
      wrapper.get('[data-testid="ai-panel-route-banner"]').text(),
    ).toContain('common.aiPanel.routedTo Agent');
    expect(
      wrapper.get('[data-testid="ai-panel-header-summary"]').text(),
    ).toContain('2 common.globalAiChat.messages');
  });

  it('renders compact utility actions with fullscreen kept behind minimize and emits each action', async () => {
    const wrapper = mount(AIChatPanelHeader, {
      props: {
        docked: true,
        mode: 'panel',
        panelTitle: 'common.aiPanel.title',
      },
    });

    const actionButtons = wrapper
      .get('[data-testid="ai-panel-primary-actions"]')
      .findAll('button');

    expect(
      actionButtons.map((button) => button.attributes('aria-label')),
    ).toEqual([
      'common.aiPanel.undock',
      'common.aiPanel.minimize',
      'common.aiPanel.fullscreen',
      'common.aiPanel.close',
    ]);

    await actionButtons[0]!.trigger('click');
    await actionButtons[1]!.trigger('click');
    await actionButtons[2]!.trigger('click');
    await actionButtons[3]!.trigger('click');

    expect(wrapper.emitted('toggleDock')).toHaveLength(1);
    expect(wrapper.emitted('minimize')).toHaveLength(1);
    expect(wrapper.emitted('toggleMode')).toHaveLength(1);
    expect(wrapper.emitted('close')).toHaveLength(1);
  });
});
