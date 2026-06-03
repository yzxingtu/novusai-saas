// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import KnowledgeBaseDocumentToolbar from '../KnowledgeBaseDocumentToolbar.vue';

describe('knowledgeBaseDocumentToolbar', () => {
  it('renders picker and reindex button only when management is allowed', async () => {
    const wrapper = mount(KnowledgeBaseDocumentToolbar, {
      props: {
        i18nPrefix: 'tenant.knowledgeBase',
        onUploadFile: vi.fn(),
        onTextSubmit: vi.fn(),
        onQASubmit: vi.fn(),
        onReindex: vi.fn(),
        onSuccess: vi.fn(),
      },
      global: {
        directives: {
          access: () => {},
        },
        stubs: {
          IconifyIcon: { template: '<i />' },
          KnowledgeDocumentPicker: { template: '<div data-testid="picker" />' },
        },
      },
    });

    expect(wrapper.find('[data-testid="picker"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('tenant.knowledgeBase.reindex.title');

    await wrapper.setProps({ canManage: false });
    expect(wrapper.find('[data-testid="picker"]').exists()).toBe(false);
  });
});
