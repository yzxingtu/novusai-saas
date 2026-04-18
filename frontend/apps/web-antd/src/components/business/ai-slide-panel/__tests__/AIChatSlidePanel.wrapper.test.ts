// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatSlidePanel from '../AIChatSlidePanel.vue';

vi.mock('../AIChatSlidePanelShell.vue', () => ({
  default: defineComponent({
    name: 'AIChatSlidePanelShellStub',
    props: {
      aiMode: { type: String, required: false },
      apiPrefix: { type: String, required: true },
      disabledCapabilities: { type: Array, required: false },
      disabledOperations: { type: Array, required: false },
      pageContextKey: { type: String, required: false },
      pendingConversationId: { type: Number, required: false },
      pendingMessage: { type: String, required: false },
      showAttachments: { type: Boolean, required: false },
      uploadUrl: { type: String, required: true },
    },
    emits: ['conversationRestored', 'messageSent'],
    template: `
      <div
        data-testid="panel-shell"
        :data-ai-mode="aiMode"
        :data-api-prefix="apiPrefix"
        :data-page-context-key="pageContextKey"
        :data-upload-url="uploadUrl"
        :data-show-attachments="String(showAttachments)"
        :data-disabled-capabilities="JSON.stringify(disabledCapabilities || [])"
        :data-disabled-operations="JSON.stringify(disabledOperations || [])"
      >
        <button
          data-testid="emit-conversation-restored"
          @click="$emit('conversationRestored')"
        />
        <button data-testid="emit-message-sent" @click="$emit('messageSent')" />
      </div>
    `,
  }),
}));

describe('aIChatSlidePanel (wrapper)', () => {
  it('forwards policy/context props and re-emits shell events', async () => {
    const wrapper = mount(AIChatSlidePanel, {
      props: {
        aiMode: 'context_only',
        apiPrefix: '/admin',
        disabledCapabilities: ['page_context'],
        disabledOperations: ['ui_click'],
        pageContextKey: 'admin.system.logs',
        pendingConversationId: 1208,
        pendingMessage: 'continue',
        showAttachments: false,
        uploadUrl: '/admin/attachments/upload',
      },
    });

    const shell = wrapper.get('[data-testid="panel-shell"]');
    expect(shell.attributes('data-ai-mode')).toBe('context_only');
    expect(shell.attributes('data-api-prefix')).toBe('/admin');
    expect(shell.attributes('data-page-context-key')).toBe('admin.system.logs');
    expect(shell.attributes('data-upload-url')).toBe(
      '/admin/attachments/upload',
    );
    expect(shell.attributes('data-show-attachments')).toBe('false');
    expect(shell.attributes('data-disabled-capabilities')).toBe(
      '["page_context"]',
    );
    expect(shell.attributes('data-disabled-operations')).toBe('["ui_click"]');

    await wrapper
      .get('[data-testid="emit-conversation-restored"]')
      .trigger('click');
    await wrapper.get('[data-testid="emit-message-sent"]').trigger('click');

    expect(wrapper.emitted('conversationRestored')).toBeTruthy();
    expect(wrapper.emitted('messageSent')).toBeTruthy();
  });
});
