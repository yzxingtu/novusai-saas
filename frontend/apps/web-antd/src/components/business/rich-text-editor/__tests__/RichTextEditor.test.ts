// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { nextTick, ref, shallowRef } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RichTextEditor from '../RichTextEditor.vue';

const mocks = vi.hoisted(() => ({
  handleImageDrop: vi.fn(() => false),
  handleImagePaste: vi.fn(() => false),
  registerSourceEditor: vi.fn(),
  updateSourceEditorRevision: vi.fn(),
  useEditorPageOps: vi.fn(),
  useRichTextEditor: vi.fn(),
}));

vi.mock('@vben/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('@tiptap/vue-3', () => ({
  EditorContent: {
    name: 'EditorContentStub',
    props: ['editor'],
    template: '<div class="editor-content-stub"></div>',
  },
}));

vi.mock('../ai/AIBubbleMenu.vue', () => ({
  default: {
    name: 'AIBubbleMenuStub',
    props: ['editor', 'loading'],
    template: '<div class="ai-bubble-menu-stub"></div>',
  },
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

vi.mock('../sourceEditorRegistry', () => ({
  registerSourceEditor: mocks.registerSourceEditor,
  updateSourceEditorRevision: mocks.updateSourceEditorRevision,
}));

vi.mock('../useEditorPageOps', () => ({
  useEditorPageOps: mocks.useEditorPageOps,
}));

vi.mock('../useEditorUpload', () => ({
  handleImageDrop: mocks.handleImageDrop,
  handleImagePaste: mocks.handleImagePaste,
}));

vi.mock('../useRichTextEditor', () => ({
  useRichTextEditor: mocks.useRichTextEditor,
}));

describe('richTextEditor', () => {
  let revision = ref(1);
  let editor = shallowRef({
    commands: {
      focus: vi.fn(),
    },
  });

  const unregisterSourceEditorMock = vi.fn();
  const setContentMock = vi.fn();
  const focusMock = vi.fn();
  const getJSONMock = vi.fn(() => ({
    type: 'doc',
    content: [{ type: 'paragraph' }],
  }));
  const getHTMLMock = vi.fn(() => '<p>Hello</p>');
  const getTextMock = vi.fn(() => 'Hello');
  const getRevisionMock = vi.fn(() => revision.value);

  beforeEach(() => {
    revision = ref(1);
    editor = shallowRef({
      commands: {
        focus: vi.fn(),
      },
    });

    unregisterSourceEditorMock.mockReset();
    setContentMock.mockReset();
    focusMock.mockReset();
    getJSONMock.mockClear();
    getHTMLMock.mockClear();
    getTextMock.mockClear();
    getRevisionMock.mockClear();
    mocks.handleImageDrop.mockClear();
    mocks.handleImagePaste.mockClear();
    mocks.registerSourceEditor.mockReset();
    mocks.updateSourceEditorRevision.mockReset();
    mocks.useEditorPageOps.mockReset();
    mocks.useRichTextEditor.mockReset();

    mocks.registerSourceEditor.mockImplementation(
      () => unregisterSourceEditorMock,
    );
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
    }));
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('registers the source editor on mount and unregisters it on unmount', () => {
    const wrapper = mount(RichTextEditor, {
      props: {
        ai: false,
        pageKey: 'tenant.docs.detail',
      },
    });

    expect(mocks.registerSourceEditor).toHaveBeenCalledOnce();
    expect(mocks.registerSourceEditor).toHaveBeenCalledWith(
      expect.objectContaining({
        editorInstanceId: 'editor-under-test',
        pageKey: 'tenant.docs.detail',
        revision: 1,
      }),
    );

    wrapper.unmount();

    expect(unregisterSourceEditorMock).toHaveBeenCalledOnce();
  });

  it('pushes revision updates into the source editor registry', async () => {
    const wrapper = mount(RichTextEditor, {
      props: {
        ai: false,
        pageKey: 'tenant.docs.detail',
      },
    });

    revision.value = 2;
    await nextTick();

    expect(mocks.updateSourceEditorRevision).toHaveBeenCalledOnce();
    expect(mocks.updateSourceEditorRevision).toHaveBeenCalledWith(
      'tenant.docs.detail',
      'editor-under-test',
      2,
    );

    wrapper.unmount();
  });

  it('throws when ai is explicitly enabled without a pageKey', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    expect(() =>
      mount(RichTextEditor, {
        props: {
          ai: true,
        },
      }),
    ).toThrowError('RichTextEditor: pageKey is required when ai=true');

    expect(mocks.useRichTextEditor).not.toHaveBeenCalled();

    warnSpy.mockRestore();
  });
});
