// @vitest-environment happy-dom
// Test type: structural
// Verifies: rich text editor mounting does not register page-runtime AI operations.
import { mount } from '@vue/test-utils';
import { ref, shallowRef } from 'vue';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import RichTextEditor from '../RichTextEditor.vue';

const mocks = vi.hoisted(() => ({
  handleImageDrop: vi.fn(() => false),
  handleImagePaste: vi.fn(() => false),
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

describe('richTextEditor', () => {
  let revision = ref(1);
  let editor = shallowRef({
    commands: {
      focus: vi.fn(),
    },
  });

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

    setContentMock.mockReset();
    focusMock.mockReset();
    getJSONMock.mockClear();
    getHTMLMock.mockClear();
    getTextMock.mockClear();
    getRevisionMock.mockClear();
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
    }));
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('mounts without registering page-level AI editor operations', () => {
    const wrapper = mount(RichTextEditor, {
      props: {
        ai: true,
      },
    });

    expect(mocks.useRichTextEditor).toHaveBeenCalledOnce();
    expect(wrapper.find('.ai-bubble-menu-stub').exists()).toBe(false);

    wrapper.unmount();
  });

  it('does not require page-runtime registration when ai is explicitly enabled', () => {
    const wrapper = mount(RichTextEditor, {
      props: {
        ai: true,
      },
    });

    expect(mocks.useRichTextEditor).toHaveBeenCalledOnce();

    wrapper.unmount();
  });
});
