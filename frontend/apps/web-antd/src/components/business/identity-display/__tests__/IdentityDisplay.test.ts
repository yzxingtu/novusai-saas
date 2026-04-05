// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import IdentityDisplay from '../IdentityDisplay.vue';

vi.mock('ant-design-vue', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    Avatar: defineComponent({
      name: 'AvatarStub',
      props: {
        size: {
          default: 40,
          type: Number,
        },
        src: {
          default: '',
          type: String,
        },
      },
      setup(props, { slots }) {
        return () =>
          h(
            'div',
            {
              'data-size': String(props.size),
              'data-src': props.src,
              'data-testid': 'avatar',
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
            'span',
            {
              'data-testid': 'tooltip',
              'data-title': props.title,
            },
            slots.default?.(),
          );
      },
    }),
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

vi.mock('#/utils/image', () => ({
  toAvatarDisplayUrl: (value: string) => `avatar:${value}`,
}));

describe('identity display', () => {
  it('falls back to #id and not assigned org text when identity fields are empty', () => {
    const wrapper = mount(IdentityDisplay, {
      props: {
        model: {
          id: 12,
          isActive: false,
        },
      },
    });

    expect(wrapper.text()).toContain('#12');
    expect(wrapper.text()).toContain('shared.identity.unassignedArchitecture');
    expect(wrapper.get('[data-testid="avatar"]').text()).toContain('1');
    expect(
      wrapper.get('[data-testid="tooltip"]').attributes()['data-title'],
    ).toBe('shared.memberPanel.item.disabled');
  });

  it('renders nickname, icon tooltips, and secondary text', () => {
    const wrapper = mount(IdentityDisplay, {
      props: {
        model: {
          avatar: '88',
          badges: [{ color: 'blue', key: 'beta', label: 'Beta' }],
          id: 7,
          isLeader: true,
          isOwner: true,
          nickname: 'Alice',
          orgNodeName: '研发一组',
          secondaryText: 'alice@example.com',
          username: 'alice.admin',
        },
      },
    });

    expect(wrapper.text()).toContain('Alice');
    expect(wrapper.text()).toContain('研发一组');
    expect(wrapper.text()).toContain('alice@example.com');
    expect(wrapper.get('[data-testid="avatar"]').attributes()['data-src']).toBe(
      'avatar:88',
    );
    expect(
      wrapper
        .findAll('[data-testid="tooltip"]')
        .map((node) => node.attributes()['data-title']),
    ).toEqual(
      expect.arrayContaining([
        'shared.memberPanel.leader',
        'shared.identity.owner',
        'Beta',
      ]),
    );
  });

  it('prefers role context for tenant users instead of architecture', () => {
    const wrapper = mount(IdentityDisplay, {
      props: {
        model: {
          id: 21,
          nickname: 'Tenant User',
          orgNodeName: '华东一区',
          roleName: '采购专员',
          userType: 'tenant_user',
          username: 'tenant.user',
        },
      },
    });

    expect(wrapper.text()).toContain('采购专员');
    expect(wrapper.text()).not.toContain('华东一区');
  });

  it('shows unassigned role fallback for tenant users without a role', () => {
    const wrapper = mount(IdentityDisplay, {
      props: {
        model: {
          id: 22,
          nickname: 'Roleless User',
          userType: 'tenant_user',
        },
      },
    });

    expect(wrapper.text()).toContain('shared.identity.unassignedRole');
  });

  it('can hide secondary text and center the avatar block for compact layouts', () => {
    const wrapper = mount(IdentityDisplay, {
      props: {
        model: {
          id: 23,
          nickname: '超级管理员',
          orgNodeName: '平台管理组',
          secondaryText: 'admin',
          username: 'admin',
        },
        showSecondaryText: false,
        verticalAlign: 'center',
      },
    });

    expect(wrapper.text()).toContain('超级管理员');
    expect(wrapper.text()).toContain('平台管理组');
    expect(wrapper.text()).not.toContain('admin');
    expect(wrapper.classes()).toContain('items-center');
    expect(wrapper.classes()).not.toContain('items-start');
  });

  it('keeps badges on one line in compact mode by prioritizing title truncation', () => {
    const wrapper = mount(IdentityDisplay, {
      props: {
        badgeWrap: 'nowrap',
        model: {
          badges: [
            { color: 'gold', key: 'leader', label: 'Leader' },
            { color: 'gold', key: 'owner', label: 'Owner' },
            { color: 'blue', key: 'type', label: 'Admin' },
          ],
          id: 24,
          nickname: '超级管理员',
          orgNodeName: '平台管理组',
        },
      },
    });

    expect(wrapper.find('.identity-display__heading').classes()).toContain(
      'identity-display__heading--nowrap',
    );
    expect(wrapper.find('.identity-display__badge-list').classes()).toContain(
      'identity-display__badge-list--nowrap',
    );
    expect(wrapper.find('.identity-display__title').classes()).toContain(
      'identity-display__title--nowrap',
    );
  });
});
