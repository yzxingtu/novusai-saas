// @vitest-environment happy-dom
/* eslint-disable vue/one-component-per-file */
import type { ChatMessage } from '#/types/ai-chat';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatMessageViewport from '../AIChatMessageViewport.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

describe('aiChatMessageViewport', () => {
  it('forwards assistant action button payload as messageIndex + value', async () => {
    const wrapper = mount(AIChatMessageViewport, {
      props: {
        apiPrefix: '/tenant',
        chatMessages: [
          {
            clientKey: 'assistant-action',
            content: '请选择',
            role: 'assistant',
          } satisfies ChatMessage,
        ],
        getPendingOpsForMessage: () => [],
        getRichTextDraftState: () => null,
        isAgentSwitch: () => false,
      },
      global: {
        stubs: {
          ChatMessageItem: defineComponent({
            name: 'ChatMessageItemStub',
            emits: ['actionClick'],
            template:
              '<button data-testid="action-btn" @click="$emit(\'actionClick\', 7, \'查看明细\')" />',
          }),
        },
      },
    });

    await wrapper.get('[data-testid="action-btn"]').trigger('click');

    expect(wrapper.emitted('actionClick')?.[0]).toEqual([7, '查看明细']);
  });
});
