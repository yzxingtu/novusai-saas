/**
 * DocumentEditor 页面感知组件级测试
 *
 * 验证富文本审计方案：DocumentEditor.vue 挂载时调用统一的富文档 AI bridge，
 * 不再自行拼接页面感知注册细节，且保留 update_title 等文档级操作。
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
const createSavePageOperationSpy = vi.fn((options: Record<string, unknown>) => ({
  ...options,
}));
const createSimplePageOperationSpy = vi.fn((options: Record<string, unknown>) => ({
  ...options,
}));
const createParameterizedPageOperationSpy = vi.fn((options: Record<string, unknown>) => ({
  ...options,
}));
const registerRichTextDocumentPageAISpy = vi.fn(() => () => {});
const waitForRichTextEditorOperationsSpy = vi.fn(async () => true);
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
      createSavePageOperation: createSavePageOperationSpy,
      createSimplePageOperation: createSimplePageOperationSpy,
      createParameterizedPageOperation: createParameterizedPageOperationSpy,
      registerRichTextDocumentPageAI: registerRichTextDocumentPageAISpy,
      waitForRichTextEditorOperations: waitForRichTextEditorOperationsSpy,
      mountRichTextEditor: mountRichTextEditorSpy,
      downloadBlob: vi.fn(),
    };
    createSavePageOperationSpy.mockClear();
    createSimplePageOperationSpy.mockClear();
    createParameterizedPageOperationSpy.mockClear();
    registerRichTextDocumentPageAISpy.mockClear();
    waitForRichTextEditorOperationsSpy.mockClear();
  });

  afterEach(() => {
    delete (globalThis as unknown as Record<string, unknown>).NovusPluginShared;
  });

  it(
    'calls the rich text document AI bridge on mount',
    async () => {
      const wrapper = mount(DocumentEditor, { props: { id: '42' }, attachTo: document.body });
      await new Promise((r) => setTimeout(r, 100));
      await wrapper.vm.$nextTick();

      expect(waitForRichTextEditorOperationsSpy).toHaveBeenCalledWith(
        EDITOR_KEY,
      );
      expect(createSavePageOperationSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'save_document',
        }),
      );
      expect(registerRichTextDocumentPageAISpy).toHaveBeenCalledWith(
        expect.objectContaining({
          pageKey: EDITOR_KEY,
          entityDescriptionAppend: expect.stringContaining(
            'update_title modifies document metadata',
          ),
          operations: expect.arrayContaining([
            expect.objectContaining({ name: 'save_document' }),
            expect.objectContaining({
              name: 'update_title',
              params: expect.any(Object),
            }),
          ]),
        }),
      );

      const options = registerRichTextDocumentPageAISpy.mock.calls[0][0];
      expect(options.documentId()).toBe(42);
      expect(options.documentTitle()).toBe('Test Doc');
      expect(options.editor()).toBe(mockEditor);

      expect(options.operations).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ name: 'save_document' }),
          expect.objectContaining({
            name: 'update_title',
            params: expect.any(Object),
          }),
        ]),
      );

      wrapper.unmount();
    },
    10000,
  );

  it(
    'passes live editor and document metadata getters to the AI bridge',
    async () => {
      const wrapper = mount(DocumentEditor, { props: { id: '42' }, attachTo: document.body });
      await new Promise((r) => setTimeout(r, 150));
      await wrapper.vm.$nextTick();

      const options = registerRichTextDocumentPageAISpy.mock.calls[0][0];
      expect(options.editor()).toBe(mockEditor);
      expect(options.documentTitle()).toBe('Test Doc');
      expect(options.entityDescriptionAppend).toMatch(
        /update_title modifies document metadata title/,
      );

      wrapper.unmount();
    },
    10000,
  );
});
