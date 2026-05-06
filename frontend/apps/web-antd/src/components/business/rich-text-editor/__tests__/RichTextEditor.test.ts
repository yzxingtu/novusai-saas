// @vitest-environment happy-dom
// 中文: 测试类型 structural + behavioral，验证富文本 AI 预览后应用闭环。
// EN: Test type structural + behavioral; verifies the rich-text AI preview-before-apply loop.
// 中文: Mock TipTap、编辑器 composable、绑定解析、富文本 SSE API；组件菜单、预览、内联对话与应用逻辑保持真实。
// EN: Mocks TipTap, editor composable, assignment resolve, and rich-text SSE API while keeping component menu, preview, inline chat, and apply behavior real.
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, ref, shallowRef } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RichTextEditor from '../RichTextEditor.vue';

const assignmentMocks = vi.hoisted(() => ({
  resolveAgentAssignmentApi: vi.fn(),
}));
const richTextAiMocks = vi.hoisted(() => ({
  streamRichTextAiOperationApi: vi.fn(),
}));
const sidePanelStoreMocks = vi.hoisted(() => ({
  useAIPanelStore: vi.fn(() => {
    throw new Error('RichTextEditor AI must stay inside the editor surface.');
  }),
}));
const mocks = vi.hoisted(() => ({
  handleImageDrop: vi.fn(() => false),
  handleImagePaste: vi.fn(() => false),
  useRichTextEditor: vi.fn(),
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
vi.mock('@tiptap/vue-3', () => ({
  EditorContent: {
    name: 'EditorContentStub',
    props: ['editor'],
    template: '<div class="editor-content-stub"></div>',
  },
}));
vi.mock('#/api/shared/agent-assignments', () => ({
  resolveAgentAssignmentApi: assignmentMocks.resolveAgentAssignmentApi,
}));
vi.mock('#/api/shared/rich-text-ai', () => ({
  streamRichTextAiOperationApi: richTextAiMocks.streamRichTextAiOperationApi,
}));
vi.mock('#/store', () => ({
  useAIPanelStore: sidePanelStoreMocks.useAIPanelStore,
}));
vi.mock('../toolbar/EditorToolbar.vue', () => ({
  default: {
    name: 'EditorToolbarStub',
    props: ['editor', 'upload', 'sourceMode'],
    emits: ['toggle-source'],
    template: '<div class="editor-toolbar-stub"></div>',
  },
}));
vi.mock('../toolbar/MiniToolbar.vue', () => ({
  default: {
    name: 'MiniToolbarStub',
    props: ['editor', 'upload'],
    template: '<div class="mini-toolbar-stub"></div>',
  },
}));
vi.mock('../useEditorUpload', () => ({
  handleImageDrop: mocks.handleImageDrop,
  handleImagePaste: mocks.handleImagePaste,
}));
vi.mock('../useRichTextEditor', () => ({
  useRichTextEditor: mocks.useRichTextEditor,
}));

const selectedSnapshot = {
  afterText: ' after context',
  beforeText: 'before context ',
  empty: false,
  from: 3,
  revision: 1,
  selectedText: 'selected text',
  to: 16,
};

const emptySnapshot = {
  afterText: ' after context',
  beforeText: 'before context ',
  empty: true,
  from: 3,
  revision: 1,
  selectedText: '',
  to: 3,
};

const chineseSnapshot = {
  afterText: ' 后文',
  beforeText: '前文 ',
  empty: false,
  from: 3,
  revision: 1,
  selectedText: '胡萝卜是兔子的刻板印象，但兔子也需要草和干草。',
  to: 28,
};

const aiWritingProps = {
  aiWriting: {
    enabled: true,
    apiPrefix: '/admin',
    documentTitle: 'Doc title',
    featureCode: 'system.ai_writing',
  },
};

interface EditorCoords {
  bottom: number;
  left: number;
  right: number;
  top: number;
}

interface EditorMock {
  commands: { focus: ReturnType<typeof vi.fn> };
  setEditable: ReturnType<typeof vi.fn>;
  view?: {
    coordsAtPos: (position: number) => EditorCoords;
  };
}

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
        output_contract: 'editor_plain_text_fragment',
        conversation_id: 71,
      });
      handlers.onEnd?.();
    },
  );
}

describe('richTextEditor', () => {
  let revision = ref(1);
  let editor = shallowRef<EditorMock>({
    commands: { focus: vi.fn() },
    setEditable: vi.fn(),
  });

  const setContentMock = vi.fn();
  const applyContentMock = vi.fn();
  const focusMock = vi.fn();
  const getJSONMock = vi.fn(() => ({
    type: 'doc',
    content: [{ type: 'paragraph' }],
  }));
  const getHTMLMock = vi.fn(() => '<p>Hello</p>');
  const getTextMock = vi.fn(() => 'Hello');
  const getRevisionMock = vi.fn(() => revision.value);
  const getSelectionSnapshotMock = vi.fn(() => selectedSnapshot);
  const validateSelectionSnapshotMock = vi.fn(() => true);

  beforeEach(() => {
    revision = ref(1);
    editor = shallowRef<EditorMock>({
      commands: { focus: vi.fn() },
      setEditable: vi.fn(),
    });
    setContentMock.mockReset();
    applyContentMock.mockReset();
    focusMock.mockReset();
    getJSONMock.mockClear();
    getHTMLMock.mockClear();
    getTextMock.mockClear();
    getRevisionMock.mockClear();
    getSelectionSnapshotMock.mockReset();
    getSelectionSnapshotMock.mockReturnValue(selectedSnapshot);
    validateSelectionSnapshotMock.mockReset();
    validateSelectionSnapshotMock.mockReturnValue(true);
    mocks.handleImageDrop.mockClear();
    mocks.handleImagePaste.mockClear();
    mocks.useRichTextEditor.mockReset();
    mocks.useRichTextEditor.mockImplementation(() => ({
      editor,
      wordCount: ref(2),
      characterCount: ref(5),
      revision,
      setContent: setContentMock,
      getJSON: getJSONMock,
      getHTML: getHTMLMock,
      getText: getTextMock,
      focus: focusMock,
      editorInstanceId: 'editor-under-test',
      getRevision: getRevisionMock,
      getSelectionSnapshot: getSelectionSnapshotMock,
      validateSelectionSnapshot: validateSelectionSnapshotMock,
      applyContent: applyContentMock,
    }));
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
    sidePanelStoreMocks.useAIPanelStore.mockClear();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('mounts as a standalone editor UI without AI writing by default', async () => {
    const wrapper = mount(RichTextEditor);

    expect(mocks.useRichTextEditor).toHaveBeenCalledOnce();
    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 20, clientY: 30 });
    await wrapper
      .find('.overflow-y-auto')
      .trigger('contextmenu', { clientX: 20, clientY: 30 });

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(false);
    expect(sidePanelStoreMocks.useAIPanelStore).not.toHaveBeenCalled();
    expect(richTextAiMocks.streamRichTextAiOperationApi).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('shows action-template backed AI actions when selected text is available', async () => {
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });

    const prompt = wrapper.get('[data-testid="rte-ai-selection-prompt"]');
    expect(prompt.attributes('role')).toBe('menu');
    for (const action of [
      'continue',
      'rewrite',
      'insert',
      'format',
      'optimize',
      'proofread',
      'translate',
      'summarize',
      'expand',
      'custom',
      'more',
    ]) {
      expect(
        wrapper.find(`[data-testid="rte-ai-action-${action}"]`).exists(),
      ).toBe(true);
    }
    expect(wrapper.find('[data-testid="rte-ai-action-row-1"]').exists()).toBe(
      true,
    );
    expect(wrapper.find('[data-testid="rte-ai-action-row-2"]').exists()).toBe(
      true,
    );
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-rewrite"]')
        .attributes('disabled'),
    ).toBeUndefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-rewrite-icon"]')
        .attributes('data-icon'),
    ).toBe('lucide:refresh-ccw-dot');
    expect(wrapper.find('[data-testid="rte-ai-preview-card"]').exists()).toBe(
      false,
    );
    wrapper.unmount();
  });

  it('opens cursor-capable actions without selected text and disables selection-only actions', async () => {
    getSelectionSnapshotMock.mockReturnValue(emptySnapshot);
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.rte-editor')
      .trigger('keydown', { key: 'F10', shiftKey: true });

    expect(
      wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists(),
    ).toBe(true);
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-continue"]')
        .attributes('disabled'),
    ).toBeUndefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-insert"]')
        .attributes('disabled'),
    ).toBeUndefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-custom"]')
        .attributes('disabled'),
    ).toBeUndefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-rewrite"]')
        .attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-translate"]')
        .attributes('disabled'),
    ).toBeDefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-format"]')
        .attributes('disabled'),
    ).toBeDefined();
    wrapper.unmount();
  });

  it('anchors the AI action layer to the editor selection coordinates', async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1400,
    });
    Object.defineProperty(window, 'innerHeight', {
      configurable: true,
      value: 900,
    });
    let scrollOffset = 0;
    const coordsAtPos = vi.fn((position: number) =>
      position === selectedSnapshot.from
        ? {
            bottom: 320 + scrollOffset,
            left: 800 + scrollOffset / 2,
            right: 802 + scrollOffset / 2,
            top: 300 + scrollOffset,
          }
        : {
            bottom: 322 + scrollOffset,
            left: 820 + scrollOffset / 2,
            right: 824 + scrollOffset / 2,
            top: 302 + scrollOffset,
          },
    );
    editor = shallowRef<EditorMock>({
      commands: { focus: vi.fn() },
      setEditable: vi.fn(),
      view: { coordsAtPos },
    });
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 20, clientY: 20 });

    const prompt = wrapper.get('[data-testid="rte-ai-selection-prompt"]');
    expect(prompt.attributes('style')).toContain('left: 492px');
    expect(prompt.attributes('style')).toContain('top: 202px');

    scrollOffset = 40;
    window.dispatchEvent(new Event('scroll'));
    await flushPromises();

    expect(prompt.attributes('style')).toContain('left: 512px');
    expect(prompt.attributes('style')).toContain('top: 242px');
    wrapper.unmount();
  });

  it('streams rewrite into an editable preview and applies it only after confirmation', async () => {
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();

    expect(assignmentMocks.resolveAgentAssignmentApi).toHaveBeenCalledWith(
      '/admin',
      'system.ai_writing',
    );
    expect(sidePanelStoreMocks.useAIPanelStore).not.toHaveBeenCalled();
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledTimes(
      1,
    );
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledWith(
      '/admin',
      'rewrite',
      expect.objectContaining({
        selected_text: 'selected text',
        before_text: 'before context ',
        after_text: ' after context',
        document_title: 'Doc title',
        surface: 'rich_text_editor',
      }),
      expect.any(Object),
      expect.objectContaining({ abortController: expect.any(AbortController) }),
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
        'selected_text',
        'surface',
      ].sort(),
    );
    expect(payload).not.toHaveProperty('selection_html');
    expect(payload).not.toHaveProperty('page_context');
    expect(payload).not.toHaveProperty('page_data');
    expect(payload).not.toHaveProperty('page_session');
    expect(payload).not.toHaveProperty('page_session_id');
    expect(payload).not.toHaveProperty('route');
    expect(payload).not.toHaveProperty('schema');
    expect(payload).not.toHaveProperty('ui_action');
    expect(payload).not.toHaveProperty('pageop_apply');
    expect(payload.target_lang).toBeUndefined();
    expect(payload.instruction).toContain('请使用英文输出');
    expect(
      (
        wrapper.get('[data-testid="rte-ai-preview-editor"]')
          .element as HTMLTextAreaElement
      ).value,
    ).toBe('AI result');
    expect(wrapper.get('[data-testid="rte-ai-preview-card"]').text()).toContain(
      '将替换原选区',
    );
    expect(wrapper.get('[data-testid="rte-ai-preview-card"]').text()).toContain(
      '输出：英文',
    );
    expect(applyContentMock).not.toHaveBeenCalled();

    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(validateSelectionSnapshotMock).toHaveBeenCalledWith(
      selectedSnapshot,
    );
    expect(applyContentMock).toHaveBeenCalledTimes(1);
    expect(applyContentMock).toHaveBeenCalledWith('AI result', {
      mode: 'replace',
      selection: selectedSnapshot,
    });
    expect(wrapper.find('[data-testid="rte-ai-preview-card"]').exists()).toBe(
      false,
    );
    wrapper.unmount();
  });

  it('clears streamed draft and blocks apply when the operation reports an error', async () => {
    richTextAiMocks.streamRichTextAiOperationApi.mockImplementation(
      async (
        _apiPrefix: string,
        _action: string,
        _payload: unknown,
        handlers: {
          onEnd?: () => void;
          onError?: (error: { event: 'error'; message: string }) => void;
          onMessage?: (delta: string) => void;
        },
      ) => {
        handlers.onMessage?.('我先把已完成部分整理给你：direct_reply。');
        handlers.onError?.({
          event: 'error',
          message: '无法连接到 AI 供应商',
        });
        handlers.onEnd?.();
      },
    );
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();

    expect(
      (
        wrapper.get('[data-testid="rte-ai-preview-editor"]')
          .element as HTMLTextAreaElement
      ).value,
    ).toBe('');
    expect(
      wrapper.get('[data-testid="rte-ai-preview-error"]').text(),
    ).toContain('无法连接到 AI 供应商');
    expect(
      wrapper
        .get('[data-testid="rte-ai-preview-apply"]')
        .attributes('disabled'),
    ).toBeDefined();

    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(applyContentMock).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('keeps Chinese selected-text operations in Chinese instead of forcing English', async () => {
    getSelectionSnapshotMock.mockReturnValue(chineseSnapshot);
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper
      .get('[data-testid="rte-ai-action-summarize"]')
      .trigger('click');
    await flushPromises();

    const [, action, payload] = richTextAiMocks.streamRichTextAiOperationApi
      .mock.calls[0] as unknown as [string, string, Record<string, unknown>];
    expect(action).toBe('summarize');
    expect(payload.target_lang).toBeUndefined();
    expect(payload.instruction).toContain('请使用中文输出');
    expect(wrapper.get('[data-testid="rte-ai-preview-card"]').text()).toContain(
      '输出：中文',
    );
    wrapper.unmount();
  });

  it('uses an adaptive target language only for translate actions', async () => {
    getSelectionSnapshotMock.mockReturnValue(selectedSnapshot);
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper
      .get('[data-testid="rte-ai-action-translate"]')
      .trigger('click');
    await flushPromises();

    const [, action, payload] = richTextAiMocks.streamRichTextAiOperationApi
      .mock.calls[0] as unknown as [string, string, Record<string, unknown>];
    expect(action).toBe('translate');
    expect(payload.target_lang).toBe('Simplified Chinese');
    expect(payload.instruction).toContain('请使用中文输出');
    expect(wrapper.get('[data-testid="rte-ai-preview-card"]').text()).toContain(
      '输出：中文',
    );
    wrapper.unmount();
  });

  it('discarding a streamed preview never writes back to the editor', async () => {
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();
    await wrapper
      .get('[data-testid="rte-ai-preview-discard"]')
      .trigger('click');

    expect(applyContentMock).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="rte-ai-preview-card"]').exists()).toBe(
      false,
    );
    wrapper.unmount();
  });

  it('fails closed when the captured selection revision or text drifted before apply', async () => {
    validateSelectionSnapshotMock.mockReturnValue(false);
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="rte-ai-preview-apply"]').trigger('click');

    expect(applyContentMock).not.toHaveBeenCalled();
    expect(
      wrapper.get('[data-testid="rte-ai-preview-error"]').text(),
    ).toContain('正文或选区已变化，请重新选择后再应用。');
    wrapper.unmount();
  });

  it('runs more/chat as an inline editor conversation without opening the side panel', async () => {
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper
      .find('.overflow-y-auto')
      .trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-more"]').trigger('click');
    await flushPromises();

    expect(sidePanelStoreMocks.useAIPanelStore).not.toHaveBeenCalled();
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledTimes(
      1,
    );
    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledWith(
      '/admin',
      'chat',
      expect.objectContaining({
        history: [],
        selected_text: 'selected text',
        surface: 'rich_text_editor',
      }),
      expect.any(Object),
      expect.objectContaining({ abortController: expect.any(AbortController) }),
    );
    expect(applyContentMock).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="rte-ai-inline-chat"]').text()).toContain(
      'AI result',
    );

    await wrapper
      .get('[data-testid="rte-ai-inline-chat-input"]')
      .setValue('再短一点');
    await wrapper
      .get('[data-testid="rte-ai-inline-chat-send"]')
      .trigger('click');
    await flushPromises();

    expect(richTextAiMocks.streamRichTextAiOperationApi).toHaveBeenCalledTimes(
      2,
    );
    const followupPayload = (
      richTextAiMocks.streamRichTextAiOperationApi.mock.calls[1] as unknown as [
        string,
        string,
        Record<string, unknown>,
      ]
    )[2];
    expect(followupPayload.instruction).toContain('再短一点');
    expect(followupPayload.history).toEqual([
      expect.objectContaining({ role: 'user' }),
      { content: 'AI result', role: 'assistant' },
    ]);

    await wrapper
      .get('[data-testid="rte-ai-inline-chat-insert"]')
      .trigger('click');
    expect(applyContentMock).toHaveBeenCalledWith('AI result', {
      mode: 'insert',
      selection: selectedSnapshot,
    });
    wrapper.unmount();
  });
});
