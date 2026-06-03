// @vitest-environment happy-dom
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
      value: {
        default: '',
        type: String,
      },
    },
    emits: ['update:value'],
    template:
      '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
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
});
