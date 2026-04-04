// @vitest-environment happy-dom

import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import { defineComponent, markRaw } from 'vue';

import { beforeEach, describe, expect, it } from 'vitest';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

import PluginFloatingPanels from '../PluginFloatingPanels.vue';

const OpsPanel = defineComponent({
  name: 'OpsPanel',
  template: '<div data-testid="ops-panel-body">Ops Panel Body</div>',
});

describe('PluginFloatingPanels', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('renders floating panel trigger, placement, and toggle content', async () => {
    const store = usePluginSlotsStore();
    store.floatingPanels = [
      {
        component: markRaw(OpsPanel),
        name: 'ops-panel',
        pluginName: 'demo-plugin',
        position: 'top-left',
        title: 'Ops Panel',
      },
    ];

    const wrapper = mount(PluginFloatingPanels);

    const panel = wrapper.get('.plugin-floating-panel');
    const trigger = wrapper.get('.plugin-floating-trigger');

    expect(panel.attributes('style')).toContain('top: 80px;');
    expect(panel.attributes('style')).toContain('left: 24px;');
    expect(trigger.attributes('title')).toBe('Ops Panel');
    expect(trigger.text()).toContain('O');
    expect(wrapper.find('[data-testid="ops-panel-body"]').exists()).toBe(false);

    await trigger.trigger('click');
    expect(wrapper.get('[data-testid="ops-panel-body"]').text()).toBe(
      'Ops Panel Body',
    );

    await trigger.trigger('click');
    expect(wrapper.find('[data-testid="ops-panel-body"]').exists()).toBe(false);
  });
});
