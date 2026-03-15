/**
 * DocumentEditor 页面感知组件级测试
 *
 * 验证富文本审计方案：DocumentEditor.vue 挂载时调用 registerPageContextExtras 与 appendPageOperations，
 * 不覆盖平台 editor ops，entity_description_append 含 update_title 语义。
 */
import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/novusdoc', () => ({
  getDoc: vi.fn().mockResolvedValue({
    document: {
      id: 42,
      title: 'Test Doc',
      content: { type: 'doc' },
      content_text: 'Sample',
      word_count: 1,
      status: 'draft',
    },
  }),
  updateDoc: vi.fn().mockResolvedValue({ document: {} }),
  getExportUrl: vi.fn(() => '#'),
  exportDocumentAsBlob: vi.fn().mockResolvedValue(new Blob([''])),
}));

import DocumentEditor from '../DocumentEditor.vue';

const EDITOR_KEY = 'tenant.plugins.novusdoc.editor.42';
const registerPageContextExtrasSpy = vi.fn(() => () => {});
const appendPageOperationsSpy = vi.fn(() => () => {});
const listPageOperationsSpy = vi.fn(() => [{ name: 'get_editor_html' }]);
const mockEditor = {
  getJSON: () => ({}),
  getHTML: () => '<p></p>',
  getText: () => 'Sample text',
  setContent: () => {},
  focus: () => {},
  destroy: () => {},
};
const mountRichTextEditorSpy = vi.fn(() => mockEditor);

describe('DocumentEditor page awareness', () => {
  beforeEach(() => {
    const win = globalThis as unknown as Record<string, unknown>;
    win.NovusPluginShared = {
      $t: (k: string) => k.split('.').pop() ?? k,
      registerPageContextExtras: registerPageContextExtrasSpy,
      appendPageOperations: appendPageOperationsSpy,
      listPageOperations: listPageOperationsSpy,
      mountRichTextEditor: mountRichTextEditorSpy,
      downloadBlob: vi.fn(),
    };
    registerPageContextExtrasSpy.mockClear();
    appendPageOperationsSpy.mockClear();
  });

  afterEach(() => {
    delete (globalThis as unknown as Record<string, unknown>).NovusPluginShared;
  });

  it(
    'calls registerPageContextExtras and appendPageOperations on mount',
    async () => {
      const wrapper = mount(DocumentEditor, { props: { id: '42' }, attachTo: document.body });
      await new Promise((r) => setTimeout(r, 100));
      await wrapper.vm.$nextTick();

      expect(registerPageContextExtrasSpy).toHaveBeenCalledWith(
        EDITOR_KEY,
        expect.any(Function),
      );
      const resolver = registerPageContextExtrasSpy.mock.calls[0][1];
      const extras = resolver();
      expect(extras).toMatchObject({
        page_key: EDITOR_KEY,
        page_data: expect.objectContaining({
          entity_description_append: expect.stringContaining('update_title modifies document metadata'),
          document_id: 42,
          document_title: 'Test Doc',
        }),
      });

      expect(appendPageOperationsSpy).toHaveBeenCalledWith(
        EDITOR_KEY,
        expect.arrayContaining([
          expect.objectContaining({ name: 'save_document' }),
          expect.objectContaining({ name: 'update_title', params: expect.any(Object) }),
        ]),
      );

      wrapper.unmount();
    },
    10000,
  );

  it(
    'extras resolver includes has_editor when editor mounted',
    async () => {
      const wrapper = mount(DocumentEditor, { props: { id: '42' }, attachTo: document.body });
      await new Promise((r) => setTimeout(r, 150));
      await wrapper.vm.$nextTick();

      const resolver = registerPageContextExtrasSpy.mock.calls[0][1];
      const extras = resolver();
      expect(extras.page_data).toMatchObject({
        has_editor: true,
        entity_description_append: expect.stringMatching(/update_title modifies document metadata title/),
      });

      wrapper.unmount();
    },
    10000,
  );
});
