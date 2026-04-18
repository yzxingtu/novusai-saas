// @vitest-environment happy-dom
import type { ChatMessage } from '../types';

import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import ChatMessageContentBlock from '../ChatMessageContentBlock.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-icon-stub" />',
  }),
}));

vi.mock('#/components/business/markdown-render', () => ({
  MarkdownRender: defineComponent({
    name: 'MarkdownRenderStub',
    props: {
      content: {
        required: true,
        type: String,
      },
      streaming: {
        default: false,
        type: Boolean,
      },
    },
    template: '<div data-testid="markdown-render-content">{{ content }}</div>',
  }),
}));

function createLongMessage(
  clientKey: string,
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    clientKey,
    content: '长消息内容'.repeat(500),
    role: 'assistant',
    streaming: false,
    ...overrides,
  };
}

describe('chatMessageContentBlock', () => {
  it('resets to collapsed state when message identity changes on the same component instance', async () => {
    const wrapper = mount(ChatMessageContentBlock, {
      props: {
        compact: true,
        index: 0,
        msg: createLongMessage('history-msg-1'),
      },
    });

    expect(wrapper.get('[data-testid="collapsed-message-hint"]').text()).toBe(
      'common.globalAiChat.collapsedMessageHint',
    );

    await wrapper.get('button').trigger('click');

    expect(
      wrapper.find('[data-testid="collapsed-message-hint"]').exists(),
    ).toBe(false);
    expect(wrapper.get('button').text()).toBe(
      'common.globalAiChat.collapseMessage',
    );

    await wrapper.setProps({
      index: 0,
      msg: createLongMessage('history-msg-2'),
    });

    expect(wrapper.get('[data-testid="collapsed-message-hint"]').text()).toBe(
      'common.globalAiChat.collapsedMessageHint',
    );
    expect(wrapper.get('button').text()).toBe('common.globalAiChat.expandMore');
  });

  it('keeps expanded state during updates for the same message identity', async () => {
    const message = createLongMessage('live-msg-1');
    const wrapper = mount(ChatMessageContentBlock, {
      props: {
        compact: true,
        index: 0,
        msg: message,
      },
    });

    await wrapper.get('button').trigger('click');
    expect(
      wrapper.find('[data-testid="collapsed-message-hint"]').exists(),
    ).toBe(false);

    await wrapper.setProps({
      msg: {
        ...message,
        content: '更新后的长消息内容'.repeat(500),
      },
    });

    expect(
      wrapper.find('[data-testid="collapsed-message-hint"]').exists(),
    ).toBe(false);
    expect(wrapper.get('button').text()).toBe(
      'common.globalAiChat.collapseMessage',
    );
  });

  it('resets expanded state when persisted message identity changes even if clientKey stays the same', async () => {
    const wrapper = mount(ChatMessageContentBlock, {
      props: {
        compact: true,
        index: 0,
        msg: {
          ...createLongMessage('shared-client-key'),
          message_id: 'message-1001',
        } as ChatMessage & { message_id: string },
      },
    });

    await wrapper.get('button').trigger('click');
    expect(
      wrapper.find('[data-testid="collapsed-message-hint"]').exists(),
    ).toBe(false);

    await wrapper.setProps({
      msg: {
        ...createLongMessage('shared-client-key'),
        message_id: 'message-2002',
      } as ChatMessage & { message_id: string },
    });

    expect(wrapper.get('[data-testid="collapsed-message-hint"]').text()).toBe(
      'common.globalAiChat.collapsedMessageHint',
    );
    expect(wrapper.get('button').text()).toBe('common.globalAiChat.expandMore');
  });
});
