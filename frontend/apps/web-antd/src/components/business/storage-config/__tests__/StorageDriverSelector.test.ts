// @vitest-environment happy-dom

import type { StorageDriverInfo } from '#/types/storage';

import { mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import StorageDriverSelector from '../StorageDriverSelector.vue';

vi.mock('ant-design-vue', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    Select: Object.assign(
      defineComponent({
        name: 'SelectStub',
        setup(_props, { slots }) {
          return () =>
            h('div', { 'data-testid': 'select-root' }, slots.default?.());
        },
      }),
      {
        Option: defineComponent({
          name: 'SelectOptionStub',
          props: {
            disabled: {
              default: false,
              type: Boolean,
            },
            value: {
              default: '',
              type: String,
            },
          },
          setup(props, { slots }) {
            return () =>
              h(
                'div',
                {
                  'data-disabled': String(props.disabled),
                  'data-testid': `option-${props.value}`,
                },
                slots.default?.(),
              );
          },
        }),
      },
    ),
    Tag: defineComponent({
      name: 'TagStub',
      props: {
        color: {
          default: '',
          type: String,
        },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'span',
            {
              'data-color': props.color,
              'data-testid': 'tag',
            },
            slots.default?.(),
          );
      },
    }),
    Tooltip: defineComponent({
      name: 'TooltipStub',
      props: {
        title: {
          default: '',
          type: String,
        },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'div',
            {
              'data-testid': 'tooltip',
              'data-title': props.title,
            },
            slots.default?.(),
          );
      },
    }),
  };
});

vi.mock('@vben/icons', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    IconifyIcon: defineComponent({
      name: 'IconifyIconStub',
      props: {
        icon: {
          default: '',
          type: String,
        },
      },
      setup(props) {
        return () =>
          h('span', {
            'data-icon': props.icon,
            'data-testid': 'icon',
          });
      },
    }),
  };
});

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

function buildDrivers(): StorageDriverInfo[] {
  return [
    {
      config_schema: null,
      display_name: 'storage.driver.local',
      is_available: true,
      is_builtin: true,
      name: 'local',
    },
    {
      config_schema: null,
      display_name: 'S3 Compatible Storage',
      is_available: true,
      is_builtin: false,
      name: 's3',
      plugin_name: 'amazon-s3',
      plugin_status: 'enabled',
    },
    {
      config_schema: null,
      display_name: 'Alibaba Cloud OSS',
      is_available: false,
      is_builtin: false,
      name: 'aliyun-oss',
      plugin_name: 'aliyun-oss',
      plugin_status: 'disabled',
    },
  ];
}

describe('storageDriverSelector', () => {
  it('renders builtin, plugin, and unavailable states for host-consumed storage drivers', () => {
    const wrapper = mount(StorageDriverSelector, {
      props: {
        drivers: buildDrivers(),
      },
    });

    expect(wrapper.get('[data-testid="option-local"]').text()).toContain(
      'shared.storage.driver.local',
    );
    expect(wrapper.get('[data-testid="option-local"]').text()).toContain(
      'shared.storage.builtin',
    );

    expect(wrapper.get('[data-testid="option-s3"]').text()).toContain(
      'S3 Compatible Storage',
    );
    expect(wrapper.get('[data-testid="option-s3"]').text()).toContain(
      'shared.storage.plugin',
    );
    expect(
      wrapper.get('[data-testid="option-aliyun-oss"]').attributes(),
    ).toMatchObject({
      'data-disabled': 'true',
    });
    expect(wrapper.get('[data-testid="option-aliyun-oss"]').text()).toContain(
      'shared.storage.unavailable',
    );
    expect(
      wrapper
        .get('[data-testid="option-aliyun-oss"] [data-testid="tooltip"]')
        .attributes()['data-title'],
    ).toBe('shared.storage.pluginNotEnabled');
  });

  it('filters out local driver when showLocal is false', () => {
    const wrapper = mount(StorageDriverSelector, {
      props: {
        drivers: buildDrivers(),
        showLocal: false,
      },
    });

    expect(wrapper.find('[data-testid="option-local"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="option-s3"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="option-aliyun-oss"]').exists()).toBe(
      true,
    );
  });
});
