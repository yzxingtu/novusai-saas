// @vitest-environment happy-dom

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatSlidePanel from '../AIChatSlidePanel.vue';

vi.mock('../AIChatSlidePanelShell.vue', () => ({
  default: defineComponent({
    name: 'AIChatSlidePanelShellStub',
    props: {
      apiPrefix: { type: String, required: true },
      pendingConversationId: { type: Number, required: false },
      pendingMessage: { type: String, required: false },
      showAttachments: { type: Boolean, required: false },
      uploadUrl: { type: String, required: true },
    },
    emits: ['conversationRestored', 'messageSent'],
    template: `
      <div
        data-testid="panel-shell"
        :data-api-prefix="apiPrefix"
        :data-upload-url="uploadUrl"
        :data-show-attachments="String(showAttachments)"
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
  it('forwards supported props and does not leak unsupported attrs', async () => {
    const wrapper = mount(AIChatSlidePanel, {
      attrs: {
        unsupportedRuntimeAttr: 'ignored',
      },
      props: {
        apiPrefix: '/admin',
        pendingConversationId: 1208,
        pendingMessage: 'continue',
        showAttachments: false,
        uploadUrl: '/admin/attachments/upload',
      },
    });

    const shell = wrapper.get('[data-testid="panel-shell"]');
    expect(shell.attributes('data-api-prefix')).toBe('/admin');
    expect(shell.attributes('data-upload-url')).toBe(
      '/admin/attachments/upload',
    );
    expect(shell.attributes('data-show-attachments')).toBe('false');
    expect(shell.attributes('data-unsupported-runtime-attr')).toBeUndefined();

    await wrapper
      .get('[data-testid="emit-conversation-restored"]')
      .trigger('click');
    await wrapper.get('[data-testid="emit-message-sent"]').trigger('click');

    expect(wrapper.emitted('conversationRestored')).toBeTruthy();
    expect(wrapper.emitted('messageSent')).toBeTruthy();
  });
});
