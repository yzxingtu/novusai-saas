import type {
  RichTextAISelectionSnapshot,
  RichTextAITask,
  RichTextDraftRuntimeState,
} from '../types';

import { mount } from '@vue/test-utils';

import { describe, expect, it, vi } from 'vitest';

import RichTextDraftCard from '../RichTextDraftCard.vue';

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

const ButtonStub = {
  props: ['block', 'disabled', 'size', 'type'],
  emits: ['click'],
  template: `
    <button
      :disabled="disabled"
      :data-block="block ? 'true' : 'false'"
      :data-size="size"
      :data-type="type"
      @click="$emit('click', $event)"
    >
      <slot />
    </button>
  `,
};

const TooltipStub = {
  props: ['title'],
  template: `
    <div class="tooltip-stub" :data-title="title">
      <slot />
    </div>
  `,
};

function createTask(
  overrides: Partial<RichTextAITask> & {
    selectionSnapshot?: Partial<RichTextAISelectionSnapshot>;
  } = {},
): RichTextAITask {
  const pageKey = overrides.pageKey ?? 'tenant.docs.detail';
  const editorInstanceId = overrides.editorInstanceId ?? 'editor-1';
  return {
    agentId: 7,
    availableModes: ['plain', 'formatted'],
    conversationId: 88,
    contextTitle: '富文档',
    createdAt: 1000,
    draft: {
      html: '<p>Formatted draft</p>',
      markdown: '**Formatted draft**',
      plainText: 'Plain draft',
    },
    editorInstanceId,
    feature: 'rewrite',
    lastAppliedMode: 'formatted',
    lastAppliedTarget: 'replace_selection',
    message: '[Rich Text Task] Rewrite',
    pageKey,
    preferredApplyMode: 'formatted',
    selectionLabel: '待改写段落',
    selectionSnapshot: {
      afterTextExcerpt: 'after',
      beforeTextExcerpt: 'before',
      editorInstanceId,
      editorRevision: 2,
      from: 4,
      pageKey,
      selectedText: '待改写段落',
      to: 12,
      ...overrides.selectionSnapshot,
    },
    state: 'ready',
    summary: '已生成一版草稿',
    taskId: 'rich-text-task-1',
    title: 'AI Rewrite',
    updatedAt: 1000,
    ...overrides,
  };
}

function createState(
  overrides: Partial<RichTextDraftRuntimeState> = {},
): RichTextDraftRuntimeState {
  return {
    canAppendToEnd: true,
    canCopy: true,
    canInsertAfterSelection: true,
    canReplaceSelection: true,
    canUndo: true,
    helperText: '原选区已变化，可复制后手动粘贴',
    lastApplyMode: 'formatted',
    lastApplyTarget: 'replace_selection',
    ...overrides,
  };
}

const testStubs = {
  AButton: ButtonStub,
  ATooltip: TooltipStub,
  Button: ButtonStub,
  IconifyIcon: true,
  Tooltip: TooltipStub,
};

describe('richTextDraftCard', () => {
  it('shows applied detail and emits apply and copy with the selected mode', async () => {
    const wrapper = mount(RichTextDraftCard, {
      props: {
        task: createTask({ state: 'applied' }),
        state: createState(),
      },
      global: {
        stubs: testStubs,
      },
    });

    expect(wrapper.text()).toContain('common.richTextDraftStateApplied');
    expect(wrapper.text()).toContain('common.richTextReplaceSelection');
    expect(wrapper.text()).toContain('common.aiWithFormat');

    await wrapper.get('[data-testid="rich-text-mode-plain"]').trigger('click');
    await wrapper.get('[data-testid="rich-text-copy"]').trigger('click');
    await wrapper
      .get('[data-testid="rich-text-apply-append_to_end"]')
      .trigger('click');

    expect(wrapper.emitted('copy')?.[0]).toEqual(['plain']);
    expect(wrapper.emitted('apply')?.[0]).toEqual(['append_to_end', 'plain']);
  });

  it('shows helper text for disabled apply actions and keeps compact buttons usable', async () => {
    const helperText = '原选区已变化，可复制后手动粘贴';
    const wrapper = mount(RichTextDraftCard, {
      props: {
        compact: true,
        task: createTask(),
        state: createState({
          canAppendToEnd: true,
          canInsertAfterSelection: false,
          canReplaceSelection: false,
          helperText,
        }),
      },
      global: {
        stubs: testStubs,
      },
    });

    expect(wrapper.text()).toContain(helperText);
    expect(
      wrapper
        .get('[data-testid="rich-text-apply-replace_selection"]')
        .attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper
        .get('[data-testid="rich-text-apply-insert_after_selection"]')
        .attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper
        .get('[data-testid="rich-text-apply-append_to_end"]')
        .attributes('disabled'),
    ).toBeUndefined();
    expect(
      wrapper.get('[data-testid="rich-text-copy"]').attributes('data-block'),
    ).toBe('true');

    const tooltipTitles = wrapper
      .findAll('.tooltip-stub')
      .map((node) => node.attributes('data-title'));
    expect(tooltipTitles).toContain(helperText);

    await wrapper.get('[data-testid="rich-text-copy"]').trigger('click');
    expect(wrapper.emitted('copy')?.[0]).toEqual(['formatted']);
  });

  it('keeps historical draft cards read-only when runtime state is missing', async () => {
    const wrapper = mount(RichTextDraftCard, {
      props: {
        task: createTask(),
        state: null,
      },
      global: {
        stubs: testStubs,
      },
    });

    expect(
      wrapper
        .get('[data-testid="rich-text-apply-replace_selection"]')
        .attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper.get('[data-testid="rich-text-discard"]').attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper.get('[data-testid="rich-text-copy"]').attributes('disabled'),
    ).toBeUndefined();

    await wrapper.get('[data-testid="rich-text-copy"]').trigger('click');
    await wrapper.get('[data-testid="rich-text-discard"]').trigger('click');

    expect(wrapper.emitted('copy')?.[0]).toEqual(['formatted']);
    expect(wrapper.emitted('discard')).toBeUndefined();
  });
});
