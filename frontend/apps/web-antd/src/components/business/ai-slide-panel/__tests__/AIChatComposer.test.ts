// @vitest-environment happy-dom
/**
 * Test type: behavioral
 * Verifies: the slide-panel composer keeps legacy mode controls hidden and enforces disabled input/send/attachment contracts.
 * Mock strategy: Ant Design Vue shell components are stubbed, while AIChatComposer event guards run real.
 */
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import AIChatComposer from '../AIChatComposer.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    template: '<span class="iconify-stub"></span>',
  }),
}));

vi.mock('ant-design-vue', () => {
  const TextArea = defineComponent({
    name: 'TextAreaStub',
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
    emits: ['keydown', 'paste', 'update:value'],
    template:
      '<textarea :disabled="disabled" :value="value" @input="$emit(\'update:value\', $event.target.value)" @keydown="$emit(\'keydown\', $event)" @paste="$emit(\'paste\', $event)" />',
  });

  return {
    Input: Object.assign(defineComponent({ template: '<div><slot /></div>' }), {
      TextArea,
    }),
    Spin: defineComponent({ template: '<div class="spin-stub" />' }),
    Tooltip: defineComponent({ template: '<div><slot /></div>' }),
  };
});

describe('aiChatComposer', () => {
  it('does not render interaction-mode controls', async () => {
    const wrapper = mount(AIChatComposer, {
      props: {
        modelValue: '',
        shiftEnterHint: 'common.globalAiChat.shiftEnterHint',
      },
    });

    const text = wrapper.text();
    expect(text).not.toContain('common.globalAiChat.modeConfirm');
    expect(text).not.toContain('common.globalAiChat.modeTrustedAuto');
    expect(text).toContain('common.globalAiChat.shiftEnterHint');
  });

  it('keeps input, attachment, and send event paths disabled while disabled', async () => {
    const wrapper = mount(AIChatComposer, {
      props: {
        attachDisabled: true,
        disabled: true,
        modelValue: '用户草稿',
        sendDisabled: true,
        shiftEnterHint: 'common.globalAiChat.shiftEnterHint',
      },
    });

    expect(wrapper.get('textarea').attributes('disabled')).toBeDefined();
    expect(
      wrapper
        .get('button[aria-label="common.globalAiChat.addAttachment"]')
        .attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper
        .get('button[aria-label="common.commandBar.send"]')
        .attributes('disabled'),
    ).toBeDefined();

    await wrapper
      .get('button[aria-label="common.commandBar.send"]')
      .trigger('click');

    expect(wrapper.emitted('send')).toBeUndefined();

    await wrapper.setProps({
      sendState: 'streaming',
    });
    await wrapper
      .get('button[aria-label="common.globalAiChat.stop"]')
      .trigger('click');

    expect(wrapper.emitted('stop')).toHaveLength(1);
  });
});
