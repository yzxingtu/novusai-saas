// @vitest-environment happy-dom

import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import { defineComponent, markRaw } from 'vue';

import { beforeEach, describe, expect, it } from 'vitest';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

import PluginNotificationUI from '../PluginNotificationUI.vue';

const BuildNotification = defineComponent({
  name: 'BuildNotification',
  props: {
    summary: {
      default: '',
      type: String,
    },
  },
  template: '<div data-testid="plugin-notification">{{ summary }}</div>',
});

describe('PluginNotificationUI', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('renders the matching plugin notification component with payload props', () => {
    const store = usePluginSlotsStore();
    store.notificationUI = [
      {
        component: markRaw(BuildNotification),
        event: 'build.finished',
        name: 'build-finished',
        pluginName: 'demo-plugin',
      },
    ];

    const wrapper = mount(PluginNotificationUI, {
      props: {
        data: {
          summary: 'Build finished successfully',
        },
        event: 'build.finished',
      },
    });

    expect(wrapper.get('[data-testid="plugin-notification"]').text()).toBe(
      'Build finished successfully',
    );
  });

  it('renders nothing when no matching plugin notification ui is registered', () => {
    const store = usePluginSlotsStore();
    store.notificationUI = [
      {
        component: markRaw(BuildNotification),
        event: 'build.finished',
        name: 'build-finished',
        pluginName: 'demo-plugin',
      },
    ];

    const wrapper = mount(PluginNotificationUI, {
      props: {
        data: {
          summary: 'Build finished successfully',
        },
        event: 'deploy.finished',
      },
    });

    expect(wrapper.find('[data-testid="plugin-notification"]').exists()).toBe(
      false,
    );
    expect(wrapper.text()).toBe('');
  });
});
