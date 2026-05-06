// @vitest-environment happy-dom
// 中文: 测试类型 behavioral，验证普通 input/textarea 复用共享文本选区 AI 浮层并写回原控件。
// EN: Test type behavioral; verifies plain inputs/textareas reuse the shared text-selection AI overlay and write back to the source control.
import type { VueWrapper } from '@vue/test-utils';

import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import GlobalPlainTextInputAiAssist from '../GlobalPlainTextInputAiAssist.vue';

const assignmentMocks = vi.hoisted(() => ({
  resolveAgentAssignmentApi: vi.fn(),
}));
const richTextAiMocks = vi.hoisted(() => ({
  streamRichTextAiOperationApi: vi.fn(),
}));

vi.mock('@vben/locales', () => ({ $t: (key: string) => key }));
vi.mock('@vben/icons', () => ({
  IconifyIcon: defineComponent({
    name: 'IconifyIconStub',
    props: {
      icon: {
        default: '',
        type: String,
      },
    },
    template: '<span class="iconify-stub" :data-icon="icon"></span>',
  }),
}));
vi.mock('#/api/shared/agent-assignments', () => ({
  resolveAgentAssignmentApi: assignmentMocks.resolveAgentAssignmentApi,
}));
vi.mock('#/api/shared/rich-text-ai', () => ({
  streamRichTextAiOperationApi: richTextAiMocks.streamRichTextAiOperationApi,
}));

function sseRewriteSuccess() {
  richTextAiMocks.streamRichTextAiOperationApi.mockImplementation(
    async (
      _apiPrefix: string,
      _action: string,
      _payload: unknown,
      handlers: {
        onDone?: (event: Record<string, unknown>) => void;
        onEnd?: () => void;
        onMessage?: (delta: string) => void;
      },
    ) => {
      handlers.onMessage?.('AI ');
      handlers.onMessage?.('result');
      handlers.onDone?.({
        event: 'done',
        action: 'rewrite',
        agent_id: 9,
        apply_strategy: 'replace_selection',
        output_contract: 'plain_text_fragment',
        conversation_id: 71,
      });
      handlers.onEnd?.();
    },
  );
}

async function flushOverlayOpen() {
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  await nextTick();
  await flushPromises();
  await nextTick();
}

describe('globalPlainTextInputAiAssist', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    assignmentMocks.resolveAgentAssignmentApi.mockReset();
    assignmentMocks.resolveAgentAssignmentApi.mockResolvedValue({
      agent_id: 9,
      agent_name: 'Writer Agent',
      config: null,
      feature_code: 'system.ai_writing',
      is_active: true,
    });
    richTextAiMocks.streamRichTextAiOperationApi.mockReset();
    sseRewriteSuccess();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    vi.restoreAllMocks();
  });

  it('opens on a selected textarea and replaces the selected text after preview apply', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/tenant', enabled: true },
    });
    const textarea = document.createElement('textarea');
    textarea.value = 'Hello selected text world';
    document.body.append(textarea);
    textarea.focus();
    textarea.setSelectionRange(6, 19);
    const inputSpy = vi.fn();
    const changeSpy = vi.fn();
    textarea.addEventListener('input', inputSpy);
    textarea.addEventListener('change', changeSpy);

    textarea.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 120, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(true);
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();

    expect(assignmentMocks.resolveAgentAssignmentApi).toHaveBeenCalledWith(
      '/tenant',
      'system.ai_writing',
    );
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledTimes(
      1,
    );
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledWith(
      '/tenant',
      'rewrite',
      expect.objectContaining({
        document_type: 'plain_text_input',
        selected_text: 'selected text',
        surface: 'plain_text_input',
      }),
      expect.any(Object),
      expect.any(Object),
    );
    const payload = (
      richTextAiMocks.streamRichTextAiOperationApi.mock.calls[0] as unknown as [
        string,
        string,
        Record<string, unknown>,
      ]
    )[2];
    expect(Object.keys(payload).sort()).toEqual(
      [
        'after_text',
        'before_text',
        'document_id',
        'document_title',
        'document_type',
        'format_instruction',
        'instruction',
        'plain_input_policy',
        'selected_text',
        'surface',
      ].sort(),
    );
    expect(payload).not.toHaveProperty('selection_html');
    expect(payload).not.toHaveProperty('page_context');
    expect(payload).not.toHaveProperty('page_data');
    expect(payload.plain_input_policy).toEqual({
      allowed_actions: [
        'continue',
        'rewrite',
        'insert',
        'optimize',
        'proofread',
        'translate',
        'summarize',
        'expand',
        'custom',
        'chat',
      ],
      enabled: true,
      field_kind: 'plain',
    });
    expect(
      (
        wrapper.get('[data-testid="rte-ai-preview-editor"]')
          .element as HTMLTextAreaElement
      ).value,
    ).toBe('AI result');

    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(textarea.value).toBe('Hello AI result world');
    expect(inputSpy).toHaveBeenCalledTimes(1);
    expect(changeSpy).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="rte-ai-preview-card"]').exists()).toBe(
      false,
    );

    wrapper.unmount();
  });

  it('does not mount selection behavior when disabled', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: false },
    });
    const input = document.createElement('input');
    input.value = 'cannot use ai here';
    document.body.append(input);
    input.focus();
    input.setSelectionRange(0, 6);

    input.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 80, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);
    expect(richTextAiMocks.streamRichTextAiOperationApi).not.toHaveBeenCalled();

    wrapper.unmount();
  });

  it('keeps the frozen input selection after focus moves to the floating menu', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const input = document.createElement('input');
    input.value = '现代化 AI 集成 SaaS 开发框架，帮助团队构建应用';
    document.body.append(input);
    input.focus();
    const selectedTitle = '现代化 AI 集成 SaaS 开发框架';
    input.setSelectionRange(0, selectedTitle.length);

    input.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 80, clientY: 80 }),
    );
    await flushOverlayOpen();
    input.setSelectionRange(0, 0);

    await wrapper
      .get('[data-testid="rte-ai-action-optimize"]')
      .trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledWith(
      '/admin',
      'optimize',
      expect.objectContaining({
        selected_text: selectedTitle,
        surface: 'plain_text_input',
      }),
      expect.any(Object),
      expect.any(Object),
    );
    expect(input.value).toBe('AI result，帮助团队构建应用');

    wrapper.unmount();
  });

  it('keeps the open menu session when another field is selected before action click', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const firstInput = document.createElement('input');
    firstInput.value = 'First selected text suffix';
    document.body.append(firstInput);
    firstInput.focus();
    firstInput.setSelectionRange(6, 19);
    firstInput.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 80, clientY: 80 }),
    );
    await flushOverlayOpen();

    const secondInput = document.createElement('input');
    secondInput.value = 'Second selected text suffix';
    document.body.append(secondInput);
    secondInput.focus();
    secondInput.setSelectionRange(7, 20);
    secondInput.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 120, clientY: 80 }),
    );
    await flushOverlayOpen();

    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledWith(
      '/admin',
      'rewrite',
      expect.objectContaining({
        selected_text: 'selected text',
        surface: 'plain_text_input',
      }),
      expect.any(Object),
      expect.any(Object),
    );
    expect(firstInput.value).toBe('First AI result suffix');
    expect(secondInput.value).toBe('Second selected text suffix');

    wrapper.unmount();
  });

  it('opens from wrapped input selections and closes when that selection collapses', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const inputWrapper = document.createElement('div');
    const input = document.createElement('input');
    input.value = '是啊';
    inputWrapper.append(input);
    document.body.append(inputWrapper);
    input.focus();
    input.setSelectionRange(0, 2);

    inputWrapper.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(true);

    input.setSelectionRange(2, 2);
    document.dispatchEvent(new Event('selectionchange'));
    input.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);

    wrapper.unmount();
  });

  it('does not open a stale menu after mouseup on a collapsed input selection', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const input = document.createElement('input');
    input.value = '是啊';
    document.body.append(input);
    input.focus();
    input.setSelectionRange(2, 2);

    input.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);

    wrapper.unmount();
  });

  it('blocks apply when the frozen input value drifted before preview apply', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const textarea = document.createElement('textarea');
    textarea.value = 'Before selected text after';
    document.body.append(textarea);
    textarea.focus();
    textarea.setSelectionRange(7, 20);

    textarea.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 90, clientY: 80 }),
    );
    await flushOverlayOpen();
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();

    textarea.value = 'Changed selected text after';
    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(textarea.value).toBe('Changed selected text after');
    expect(wrapper.find('[data-testid="rte-ai-preview-card"]').exists()).toBe(
      true,
    );
    expect(
      wrapper.find('[data-testid="rte-ai-preview-error"]').text(),
    ).toContain('正文或选区已变化');

    wrapper.unmount();
  });

  it('uses surface-aware actions for single-line inputs, textareas, and allowlists', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const input = document.createElement('input');
    input.value = 'short selected title';
    document.body.append(input);
    input.focus();
    input.setSelectionRange(6, 14);
    input.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 80, clientY: 80 }),
    );
    await flushOverlayOpen();

    const inputPrompt = wrapper.get('[data-testid="rte-ai-selection-prompt"]')
      .element as HTMLElement;
    const inputPromptWidth = Number.parseFloat(inputPrompt.style.width);
    expect(inputPromptWidth).toBeGreaterThanOrEqual(320);
    expect(inputPromptWidth).toBeLessThanOrEqual(460);
    expect(
      wrapper.get('[data-testid="rte-ai-action-translate"]').classes(),
    ).toContain('flex-none');
    expect(
      wrapper.find('[data-testid="rte-ai-action-optimize"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="rte-ai-action-continue"]').exists(),
    ).toBe(false);
    expect(wrapper.find('[data-testid="rte-ai-action-insert"]').exists()).toBe(
      false,
    );
    await assistClose(wrapper);

    const textarea = document.createElement('textarea');
    textarea.value = 'long selected content for textarea';
    document.body.append(textarea);
    textarea.focus();
    textarea.setSelectionRange(5, 21);
    textarea.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 100, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-action-continue"]').exists(),
    ).toBe(true);
    expect(wrapper.find('[data-testid="rte-ai-action-insert"]').exists()).toBe(
      true,
    );
    await assistClose(wrapper);

    const allowlisted = document.createElement('textarea');
    allowlisted.value = 'allowlisted selected content';
    allowlisted.dataset.inputAiAssistActions = 'proofread,translate';
    document.body.append(allowlisted);
    allowlisted.focus();
    allowlisted.setSelectionRange(12, 20);
    allowlisted.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 120, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-action-proofread"]').exists(),
    ).toBe(true);
    expect(
      wrapper.find('[data-testid="rte-ai-action-translate"]').exists(),
    ).toBe(true);
    expect(wrapper.find('[data-testid="rte-ai-action-rewrite"]').exists()).toBe(
      false,
    );

    await assistClose(wrapper);

    const plainInputWithFormatAllowlist = document.createElement('input');
    plainInputWithFormatAllowlist.value = 'plain selected text';
    plainInputWithFormatAllowlist.dataset.inputAiAssistActions = 'format';
    document.body.append(plainInputWithFormatAllowlist);
    plainInputWithFormatAllowlist.focus();
    plainInputWithFormatAllowlist.setSelectionRange(6, 14);
    plainInputWithFormatAllowlist.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 120, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);

    const invalidAllowlist = document.createElement('textarea');
    invalidAllowlist.value = 'invalid selected content';
    invalidAllowlist.dataset.inputAiAssistActions = 'unknown_action';
    document.body.append(invalidAllowlist);
    invalidAllowlist.focus();
    invalidAllowlist.setSelectionRange(8, 16);
    invalidAllowlist.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 120, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);

    const descriptionFormat = document.createElement('textarea');
    descriptionFormat.value = 'description selected content';
    descriptionFormat.dataset.inputAiAssistKind = 'description';
    descriptionFormat.dataset.inputAiAssistActions = 'format,chat';
    document.body.append(descriptionFormat);
    descriptionFormat.focus();
    descriptionFormat.setSelectionRange(12, 20);
    descriptionFormat.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 120, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(wrapper.find('[data-testid="rte-ai-action-format"]').exists()).toBe(
      true,
    );
    expect(wrapper.find('[data-testid="rte-ai-action-more"]').exists()).toBe(
      true,
    );
    expect(
      wrapper.find('[data-testid="rte-ai-action-proofread"]').exists(),
    ).toBe(false);

    wrapper.unmount();
  });

  it('keeps writing Q&A inside the local floating layer', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const textarea = document.createElement('textarea');
    textarea.value = 'selected content for local dialogue';
    document.body.append(textarea);
    textarea.focus();
    textarea.setSelectionRange(0, 16);

    textarea.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 90, clientY: 80 }),
    );
    await flushOverlayOpen();

    await wrapper.get('[data-testid="rte-ai-action-more"]').trigger('click');
    await flushPromises();

    expect(wrapper.find('[data-testid="rte-ai-inline-chat"]').exists()).toBe(
      true,
    );
    expect(wrapper.find('[data-testid="rte-ai-preview-card"]').exists()).toBe(
      false,
    );
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledWith(
      '/admin',
      'chat',
      expect.objectContaining({
        history: [],
        selected_text: 'selected content',
        surface: 'plain_text_input',
      }),
      expect.any(Object),
      expect.any(Object),
    );
    expect(textarea.value).toBe('selected content for local dialogue');

    wrapper.unmount();
  });

  it('skips sensitive fields and explicit opt-out controls', async () => {
    const wrapper = mount(GlobalPlainTextInputAiAssist, {
      attachTo: document.body,
      props: { apiPrefix: '/admin', enabled: true },
    });
    const password = document.createElement('input');
    password.type = 'password';
    password.value = 'secret value';
    document.body.append(password);
    password.focus();
    password.setSelectionRange(0, 6);
    password.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 80, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);

    const input = document.createElement('input');
    input.value = 'disabled selected text';
    input.dataset.inputAiAssist = 'off';
    document.body.append(input);
    input.focus();
    input.setSelectionRange(9, 17);
    input.dispatchEvent(
      new MouseEvent('mouseup', { bubbles: true, clientX: 80, clientY: 80 }),
    );
    await flushOverlayOpen();

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);
    expect(richTextAiMocks.streamRichTextAiOperationApi).not.toHaveBeenCalled();

    wrapper.unmount();
  });
});

async function assistClose(wrapper: VueWrapper) {
  const closeButton = wrapper.find(
    '[data-testid="rte-ai-selection-prompt-close"]',
  );
  if (closeButton.exists()) {
    await closeButton.trigger('click');
    await flushOverlayOpen();
  }
}
