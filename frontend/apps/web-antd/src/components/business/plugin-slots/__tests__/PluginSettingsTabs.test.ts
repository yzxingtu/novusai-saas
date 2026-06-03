// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';
import { defineComponent, markRaw, nextTick } from 'vue';

import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { usePluginSlotsStore } from '#/stores/plugin-slots';

import PluginSettingsTabs from '../PluginSettingsTabs.vue';

const GeneralTab = defineComponent({
  name: 'GeneralTab',
  template: '<div data-testid="general-tab">General Settings</div>',
});

const SecurityTab = defineComponent({
  name: 'SecurityTab',
  template: '<div data-testid="security-tab">Security Settings</div>',
});

const TabsStub = defineComponent({
  name: 'ATabsStub',
  props: {
    activeKey: {
      default: '',
      type: String,
    },
  },
  template:
    '<div class="tabs-stub" :data-active-key="activeKey"><slot /></div>',
});

const TabPaneStub = defineComponent({
  name: 'ATabPaneStub',
  props: {
    tab: {
      default: '',
      type: String,
    },
  },
  template:
    '<section class="tab-pane-stub"><h3>{{ tab }}</h3><slot /></section>',
});

describe('pluginSettingsTabs', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('renders plugin settings tabs and reacts to slot refresh', async () => {
    const store = usePluginSlotsStore();
    store.settingsTabs = [
      {
        component: markRaw(GeneralTab),
        name: 'general',
        pluginName: 'demo-plugin',
        title: 'General',
      },
      {
        component: markRaw(SecurityTab),
        name: 'security',
        pluginName: 'demo-plugin',
        title: 'Security',
      },
    ];

    const wrapper = mount(PluginSettingsTabs, {
      global: {
        stubs: {
          'a-tab-pane': TabPaneStub,
          'a-tabs': TabsStub,
        },
      },
    });

    expect(wrapper.text()).toContain('General');
    expect(wrapper.text()).toContain('Security');
    expect(wrapper.get('[data-testid="general-tab"]').text()).toBe(
      'General Settings',
    );
    expect(wrapper.get('[data-testid="security-tab"]').text()).toBe(
      'Security Settings',
    );

    store.settingsTabs = [
      {
        component: markRaw(SecurityTab),
        name: 'security',
        pluginName: 'demo-plugin',
        title: 'Security',
      },
    ];
    await nextTick();

    expect(wrapper.text()).not.toContain('General');
    expect(wrapper.text()).toContain('Security');
    expect(wrapper.find('[data-testid="general-tab"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="security-tab"]').text()).toBe(
      'Security Settings',
    );
  });

  it('renders nothing when no plugin settings tabs are registered', () => {
    const wrapper = mount(PluginSettingsTabs, {
      global: {
        stubs: {
          'a-tab-pane': TabPaneStub,
          'a-tabs': TabsStub,
        },
      },
    });

    expect(wrapper.text()).toBe('');
    expect(wrapper.find('.tabs-stub').exists()).toBe(false);
  });
});
