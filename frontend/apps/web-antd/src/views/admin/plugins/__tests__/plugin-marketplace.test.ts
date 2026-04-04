import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, h, reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PluginMarketplacePage from '../marketplace/index.vue';

const mockRefs = vi.hoisted(() => ({
  getMarketplaceListApi: vi.fn(),
  openMarketplace: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock('#/api/admin/plugin-marketplace', () => ({
  getMarketplaceListApi: mockRefs.getMarketplaceListApi,
}));

vi.mock('#/composables/use-page-ai-registration', () => ({
  usePageAIRegistration: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('../data', () => ({
  getTierColor: () => 'blue',
  getTierText: () => 'tier',
}));

vi.mock('@vben/common-ui', () => ({
  Page: defineComponent({
    name: 'Page',
    setup(_props, { slots }) {
      return () => h('div', slots.default?.());
    },
  }),
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIcon',
    setup() {
      return () => h('i');
    },
  }),
}));

vi.mock('vue-router', () => {
  const route = reactive({
    query: {},
  });

  return {
    useRoute: () => route,
    useRouter: () => ({
      push: mockRefs.routerPush,
      replace: mockRefs.routerReplace,
    }),
  };
});

vi.mock('../modules/PluginInstallWizard.vue', () => ({
  default: defineComponent({
    name: 'PluginInstallWizard',
    setup(_props, { expose }) {
      expose({
        openMarketplace: mockRefs.openMarketplace,
      });
      return () => h('div');
    },
  }),
}));

vi.mock('../marketplace/MarketplaceSettingsModal.vue', () => ({
  default: defineComponent({
    name: 'MarketplaceSettingsModal',
    setup() {
      return () => h('div');
    },
  }),
}));

vi.mock('../marketplace/SkillRegistryPanel.vue', () => ({
  default: defineComponent({
    name: 'SkillRegistryPanel',
    setup() {
      return () => h('div');
    },
  }),
}));

vi.mock('ant-design-vue', () => {
  const ButtonStub = defineComponent({
    name: 'AButton',
    emits: ['click'],
    setup(_props, { emit, slots }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.());
    },
  });

  const SearchStub = defineComponent({
    name: 'AInputSearch',
    emits: ['search', 'update:value'],
    setup(_props, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const SelectStub = defineComponent({
    name: 'ASelect',
    setup(_props, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const SelectOptionStub = defineComponent({
    name: 'ASelectOption',
    setup(_props, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const SpinStub = defineComponent({
    name: 'ASpin',
    setup(_props, { slots }) {
      return () => h('div', slots.default?.());
    },
  });

  const TagStub = defineComponent({
    name: 'ATag',
    setup(_props, { slots }) {
      return () => h('span', slots.default?.());
    },
  });

  return {
    Button: ButtonStub,
    Input: {
      Search: SearchStub,
    },
    Pagination: defineComponent({
      name: 'APagination',
      setup() {
        return () => h('div');
      },
    }),
    Select: SelectStub,
    SelectOption: SelectOptionStub,
    Spin: SpinStub,
    Tag: TagStub,
  };
});

describe('plugin marketplace page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRefs.openMarketplace.mockResolvedValue(undefined);
    mockRefs.getMarketplaceListApi.mockResolvedValue({
      items: [
        {
          name: 'weather-widget',
          slug: 'weather-widget',
          display_name: 'Weather Widget',
          description: 'Shows current weather.',
          icon: 'lucide:cloud',
          version: '1.2.3',
          author: 'NovusAI',
          tier: 'official',
          pricing_type: 'free',
          price: null,
          rating: 4.8,
          downloads: 128,
          tags: ['weather'],
          is_installed: false,
          installed_version: null,
        },
      ],
      total: 1,
    });
  });

  it('routes marketplace installs through the shared install wizard', async () => {
    const wrapper = mount(PluginMarketplacePage, {
      global: {
        directives: {
          access: {},
        },
      },
    });

    await flushPromises();

    const installButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('admin.plugin.marketplace.install'));

    expect(installButton).toBeTruthy();
    await installButton!.trigger('click');

    expect(mockRefs.openMarketplace).toHaveBeenCalledWith(
      expect.objectContaining({
        slug: 'weather-widget',
        name: 'weather-widget',
      }),
    );
  });
});
