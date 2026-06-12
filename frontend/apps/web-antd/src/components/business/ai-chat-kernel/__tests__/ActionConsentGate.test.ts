// Test type: component
// Verifies: approval presentation cards render user-readable fields while
// keeping technical payload collapsed and preserving legacy preview fallback.
// Mock strategy: i18n and icon rendering only; component display logic is real.
// @vitest-environment happy-dom
import type { KernelPendingActionState } from '../TurnFlowState';

import { mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import ActionConsentGate from '../ActionConsentGate.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: {
    name: 'IconifyIcon',
    props: ['icon'],
    template: '<i :data-icon="icon"></i>',
  },
}));

describe('action consent gate', () => {
  it('renders approval presentation fields and hides sensitive details', () => {
    const action: KernelPendingActionState = {
      action: 'POST /admin/plans',
      approvalPresentation: {
        details: [
          { label: '套餐名称', value: '测试套餐' },
          { label: '价格', value: '599' },
          { label: 'password', sensitive: true, value: 'secret-value' },
        ],
        menu_label: '套餐管理',
        permission_code: 'tenant_plan:create',
        risk_level: 'medium',
        summary: 'AI 助手将执行「套餐管理」下的「创建套餐」操作。',
        target: { name: '测试套餐', type: '套餐' },
        technical: { operation_id: 'create_tenant_plan' },
        title: '创建套餐',
      },
      kind: 'confirmation',
      preview: { body: { name: '测试套餐', password: 'secret-value' } },
      toolName: 'invoke_internal_operation',
    };

    const wrapper = mount(ActionConsentGate, {
      props: { action, compact: true },
    });

    expect(wrapper.text()).toContain('创建套餐');
    expect(wrapper.text()).toContain('套餐管理');
    expect(wrapper.text()).toContain('tenant_plan:create');
    expect(wrapper.text()).toContain('套餐名称');
    expect(wrapper.text()).toContain('测试套餐');
    expect(
      wrapper.find('[data-testid="approval-fallback-preview"]').exists(),
    ).toBe(false);

    const detailArea = wrapper.find(
      '[data-testid="approval-presentation-details"]',
    );
    expect(detailArea.text()).not.toContain('password');
    expect(detailArea.text()).not.toContain('secret-value');

    const technical = wrapper.find(
      '[data-testid="approval-technical-details"]',
    );
    expect(technical.exists()).toBe(true);
    expect(technical.element.hasAttribute('open')).toBe(false);
    expect(technical.text()).toContain('create_tenant_plan');
  });

  it('keeps legacy preview fallback visible when presentation is absent', () => {
    const action: KernelPendingActionState = {
      action: 'query',
      kind: 'confirmation',
      preview: {
        sql: 'SELECT 1',
        table: 'ai_call_logs',
      },
      table: 'ai_call_logs',
      toolName: 'query_records',
    };

    const wrapper = mount(ActionConsentGate, {
      props: { action, compact: true },
    });

    const fallback = wrapper.find('[data-testid="approval-fallback-preview"]');
    expect(fallback.exists()).toBe(true);
    expect(fallback.text()).toContain('sql');
    expect(fallback.text()).toContain('SELECT 1');
    expect(
      wrapper.find('[data-testid="approval-technical-details"]').exists(),
    ).toBe(false);
  });
});
