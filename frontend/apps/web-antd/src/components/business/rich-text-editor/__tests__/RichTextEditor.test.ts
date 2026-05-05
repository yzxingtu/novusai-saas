// @vitest-environment happy-dom
// Test type: structural + behavioral
// Verifies: RichTextEditor stays standalone by default, exposes only a lightweight selection AI prompt, resolves system.ai_writing, and delegates explicit editor-domain prompts to the global AI panel.
// Mock strategy: TipTap rendering, editor composable, assignment resolver, and global AI panel store are mocked; RichTextEditor selection UI and message-building behavior run real.
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, ref, shallowRef } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RichTextEditor from '../RichTextEditor.vue';

const assignmentMocks = vi.hoisted(() => ({ resolveAgentAssignmentApi: vi.fn() }));
const aiPanelMocks = vi.hoisted(() => ({
  openWithAgent: vi.fn(),
  openWithContext: vi.fn(() => true),
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
    props: ['icon'],
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
vi.mock('#/store', () => ({
  useAIPanelStore: () => aiPanelMocks,
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
vi.mock('../useRichTextEditor', () => ({ useRichTextEditor: mocks.useRichTextEditor }));

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
  afterText: '',
  beforeText: '',
  empty: true,
  from: 3,
  revision: 1,
  selectedText: '',
  to: 3,
};

const aiWritingProps = {
  aiWriting: {
    enabled: true,
    apiPrefix: '/admin',
    documentTitle: 'Doc title',
    featureCode: 'system.ai_writing',
  },
};

const legacyContextMenuTestId = `rte-ai-${'context'}-menu`;
const legacyBubbleButtonTestId = `rte-ai-${'bubble'}-button`;
const legacyPreviewCardTestId = `rte-ai-${'preview'}-card`;
const legacyLoadingCardTestId = `rte-ai-${'loading'}-card`;
const legacyErrorCardTestId = `rte-ai-${'error'}-card`;
const legacyWritingEndpointFragment = `/ai/${'writing'}`;

describe('richTextEditor', () => {
  let revision = ref(1);
  let editor = shallowRef({
    commands: { focus: vi.fn() },
    setEditable: vi.fn(),
  });

  const setContentMock = vi.fn();
  const applyContentMock = vi.fn();
  const focusMock = vi.fn();
  const getJSONMock = vi.fn(() => ({ type: 'doc', content: [{ type: 'paragraph' }] }));
  const getHTMLMock = vi.fn(() => '<p>Hello</p>');
  const getTextMock = vi.fn(() => 'Hello');
  const getRevisionMock = vi.fn(() => revision.value);
  const getSelectionSnapshotMock = vi.fn(() => selectedSnapshot);

  beforeEach(() => {
    revision = ref(1);
    editor = shallowRef({ commands: { focus: vi.fn() }, setEditable: vi.fn() });
    setContentMock.mockReset();
    applyContentMock.mockReset();
    focusMock.mockReset();
    getJSONMock.mockClear();
    getHTMLMock.mockClear();
    getTextMock.mockClear();
    getRevisionMock.mockClear();
    getSelectionSnapshotMock.mockReset();
    getSelectionSnapshotMock.mockReturnValue(selectedSnapshot);
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
    aiPanelMocks.openWithAgent.mockReset();
    aiPanelMocks.openWithContext.mockReset();
    aiPanelMocks.openWithContext.mockReturnValue(true);
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('mounts as a standalone editor UI without AI writing by default', async () => {
    const wrapper = mount(RichTextEditor);

    expect(mocks.useRichTextEditor).toHaveBeenCalledOnce();
    await wrapper.find('.overflow-y-auto').trigger('mouseup', { clientX: 20, clientY: 30 });
    await wrapper.find('.overflow-y-auto').trigger('contextmenu', { clientX: 20, clientY: 30 });

    expect(wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists()).toBe(false);
    expect(wrapper.find(`[data-testid="${legacyContextMenuTestId}"]`).exists()).toBe(false);
    expect(wrapper.find(`[data-testid="${legacyBubbleButtonTestId}"]`).exists()).toBe(false);
    expect(aiPanelMocks.openWithContext).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('shows only the lightweight selection prompt when selected text is available', async () => {
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper.find('.overflow-y-auto').trigger('mouseup', { clientX: 120, clientY: 80 });

    const prompt = wrapper.get('[data-testid="rte-ai-selection-prompt"]');
    expect(prompt.attributes('role')).toBe('menu');
    expect(wrapper.find('[data-testid="rte-ai-trigger-icon"]').exists()).toBe(true);
    expect(prompt.text()).not.toContain('原选区');
    expect(prompt.text()).not.toContain('selected text');
    expect(wrapper.get('[data-testid="rte-ai-action-continue"]').attributes('disabled')).toBeUndefined();
    expect(wrapper.get('[data-testid="rte-ai-action-rewrite"]').attributes('disabled')).toBeUndefined();
    expect(
      wrapper
        .get('[data-testid="rte-ai-action-rewrite-icon"]')
        .attributes('data-icon'),
    ).toBe('lucide:refresh-ccw-dot');
    expect(wrapper.get('[data-testid="rte-ai-action-insert"]').attributes('disabled')).toBeUndefined();
    expect(wrapper.get('[data-testid="rte-ai-action-format"]').attributes('disabled')).toBeUndefined();
    expect(wrapper.get('[data-testid="rte-ai-action-more"]').attributes('disabled')).toBeUndefined();
    expect(wrapper.find(`[data-testid="${legacyContextMenuTestId}"]`).exists()).toBe(false);
    expect(wrapper.find(`[data-testid="${legacyPreviewCardTestId}"]`).exists()).toBe(false);
    expect(wrapper.find(`[data-testid="${legacyLoadingCardTestId}"]`).exists()).toBe(false);
    expect(wrapper.find(`[data-testid="${legacyErrorCardTestId}"]`).exists()).toBe(false);
    wrapper.unmount();
  });

  it('does not show the selection prompt when there is no selected text', async () => {
    getSelectionSnapshotMock.mockReturnValue(emptySnapshot);
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper.find('.overflow-y-auto').trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.find('.rte-editor').trigger('keydown', { key: 'F10', shiftKey: true });

    expect(wrapper.find('[data-testid="rte-ai-selection-prompt"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="rte-ai-notice"]').text()).toContain('请先选择要处理的文本。');
    expect(aiPanelMocks.openWithContext).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('resolves system.ai_writing and opens the global AI panel with explicit editor selection context', async () => {
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper.find('.overflow-y-auto').trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();

    expect(assignmentMocks.resolveAgentAssignmentApi).toHaveBeenCalledTimes(1);
    expect(assignmentMocks.resolveAgentAssignmentApi).toHaveBeenCalledWith('/admin', 'system.ai_writing');
    expect(aiPanelMocks.openWithAgent).not.toHaveBeenCalled();
    expect(aiPanelMocks.openWithContext).toHaveBeenCalledTimes(1);
    expect(aiPanelMocks.openWithContext).toHaveBeenCalledWith({
      agentId: 9,
      message: expect.any(String),
    });

    const [panelOptions] = aiPanelMocks.openWithContext.mock.calls[0] as unknown as [
      { agentId: number; message: string },
    ];
    const message = panelOptions.message;
    expect(message).toContain('文档写作助手：改写');
    expect(message).toContain('标题：Doc title');
    expect(message).toContain('selected text');
    expect(message).toContain('before context');
    expect(message).toContain('after context');
    expect(message).toContain('范围：editor=editor-under-test; revision=1; range=3-16');
    expect(message).not.toContain('请作为文档写作助手处理以下富文本编辑器选区。');
    expect(message).not.toContain('选区前文（仅供参考）：');
    const forbiddenPayloadFragments = [
      `page${'_'}context`,
      `page${'_'}session`,
      `page${'_'}data`,
      `page${'_'}session${'_'}id`,
      `ui${'_'}action`,
      `pageop${'_'}action`,
      legacyWritingEndpointFragment,
    ];
    for (const fragment of forbiddenPayloadFragments) {
      expect(message).not.toContain(fragment);
    }
    expect(applyContentMock).not.toHaveBeenCalled();
    expect(wrapper.find(`[data-testid="${legacyPreviewCardTestId}"]`).exists()).toBe(false);
    expect(wrapper.get('[data-testid="rte-ai-notice"]').text()).toContain('已打开右侧 AI 对话：Writer Agent');
    wrapper.unmount();
  });

  it('fails closed and does not open the global panel when system.ai_writing is unassigned', async () => {
    assignmentMocks.resolveAgentAssignmentApi.mockImplementation(
      async (_apiPrefix: string, featureCode: string) => ({
        agent_id: null,
        agent_name: null,
        config: null,
        feature_code: featureCode,
        is_active: true,
      }),
    );
    const wrapper = mount(RichTextEditor, { props: aiWritingProps });

    await wrapper.find('.overflow-y-auto').trigger('mouseup', { clientX: 120, clientY: 80 });
    await wrapper.get('[data-testid="rte-ai-action-rewrite"]').trigger('click');
    await flushPromises();

    expect(assignmentMocks.resolveAgentAssignmentApi).toHaveBeenCalledWith(
      '/admin',
      'system.ai_writing',
    );
    expect(aiPanelMocks.openWithContext).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="rte-ai-notice"]').text()).toContain(
      '尚未配置文档写作助手，请到「功能分配」为 system.ai_writing 绑定智能体。',
    );
    wrapper.unmount();
  });
});
