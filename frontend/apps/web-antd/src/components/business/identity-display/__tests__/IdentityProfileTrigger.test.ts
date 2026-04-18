// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import IdentityProfileTrigger from '../IdentityProfileTrigger.vue';

const dialogMocks = vi.hoisted(() => ({
  openIdentityDetailDialog: vi.fn(),
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('../use-identity-detail-dialog', () => ({
  openIdentityDetailDialog: dialogMocks.openIdentityDetailDialog,
}));

vi.mock('../IdentityQuickCard.vue', () => ({
  default: {
    name: 'IdentityQuickCardStub',
    template: '<div data-testid="quick-card">quick-card</div>',
  },
}));

vi.mock('../IdentityDisplay.vue', () => ({
  default: {
    name: 'IdentityDisplayStub',
    props: ['model'],
    template:
      '<div data-testid="identity-display">{{ model.nickname || model.username }}</div>',
  },
}));

vi.mock('ant-design-vue', async () => {
  const { defineComponent, h } = await import('vue');

  return {
    Popover: defineComponent({
      name: 'PopoverStub',
      setup(_, { slots }) {
        return () =>
          h('div', { class: 'popover-stub', 'data-testid': 'popover' }, [
            slots.default?.(),
            h('div', { 'data-testid': 'popover-content' }, slots.content?.()),
          ]);
      },
    }),
  };
});

function setMatchMediaState(options: { hover: boolean; pointerFine: boolean }) {
  const matchMedia = vi.fn((query: string) => {
    let matches = false;
    if (query === '(hover: hover)') {
      matches = options.hover;
    } else if (query === '(pointer: fine)') {
      matches = options.pointerFine;
    }
    return {
      addEventListener: vi.fn(),
      matches,
      removeEventListener: vi.fn(),
    };
  });

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: matchMedia,
    writable: true,
  });
}

describe('identityProfileTrigger', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a popover quick card on fine pointer devices', async () => {
    setMatchMediaState({ hover: true, pointerFine: true });

    const wrapper = mount(IdentityProfileTrigger, {
      props: {
        detailRequest: {
          id: 1,
          scope: 'tenant',
          subjectType: 'tenant_user',
        },
        model: {
          id: 1,
          nickname: '采购员',
          userType: 'tenant_user',
          username: 'buyer',
        },
      },
    });

    await wrapper.vm.$nextTick();

    expect(wrapper.find('[data-testid="popover"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="quick-card"]').exists()).toBe(true);
  });

  it('does not render a hover quick card on coarse pointer devices and clicks open the drawer', async () => {
    setMatchMediaState({ hover: false, pointerFine: false });
    dialogMocks.openIdentityDetailDialog.mockResolvedValue(undefined);

    const wrapper = mount(IdentityProfileTrigger, {
      props: {
        detailRequest: {
          fallback: {
            tenantName: 'Nova Tenant',
          },
          id: 2,
          scope: 'tenant',
          subjectType: 'tenant_user',
        },
        model: {
          id: 2,
          nickname: '采购员',
          userType: 'tenant_user',
          username: 'buyer',
        },
      },
    });

    expect(wrapper.find('[data-testid="popover"]').exists()).toBe(false);

    await wrapper.get('button').trigger('click');

    expect(dialogMocks.openIdentityDetailDialog).toHaveBeenCalledWith(
      expect.objectContaining({
        fallback: expect.objectContaining({
          tenantName: 'Nova Tenant',
          username: 'buyer',
        }),
        id: 2,
      }),
    );
  });

  it('opens the drawer on Enter and Space and exposes dialog a11y attributes', async () => {
    setMatchMediaState({ hover: true, pointerFine: true });
    dialogMocks.openIdentityDetailDialog.mockResolvedValue(undefined);

    const wrapper = mount(IdentityProfileTrigger, {
      props: {
        detailRequest: {
          id: 3,
          scope: 'admin',
          subjectType: 'admin',
        },
        model: {
          id: 3,
          nickname: '平台管理员',
          userType: 'admin',
          username: 'platform.admin',
        },
      },
    });

    const button = wrapper.get('button');
    expect(button.attributes()['aria-haspopup']).toBe('dialog');
    expect(button.attributes()['aria-label']).toContain(
      'shared.identity.action.openDialogAria',
    );

    await button.trigger('keydown', { key: 'Enter' });
    await button.trigger('keydown', { key: ' ' });

    expect(dialogMocks.openIdentityDetailDialog).toHaveBeenCalledTimes(2);
  });
});
