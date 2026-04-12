import { mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  listFolders: vi.fn(),
  listDocs: vi.fn(),
  searchDocs: vi.fn(),
  createDoc: vi.fn(),
  deleteDoc: vi.fn(),
  createFolder: vi.fn(),
  deleteFolder: vi.fn(),
  getDoc: vi.fn(),
  updateDoc: vi.fn(),
  getExportUrl: vi.fn(),
  exportDocumentAsBlob: vi.fn(),
}));

vi.mock('../../api/novusdoc', () => apiMocks);

import DocumentEditor from '../DocumentEditor.vue';
import DocumentList from '../DocumentList.vue';

const accessState = {
  codes: [] as string[],
};

const mockEditor = {
  getJSON: vi.fn(() => ({})),
  getHTML: vi.fn(() => '<p></p>'),
  getText: vi.fn(() => 'Sample text'),
  setContent: vi.fn(),
  focus: vi.fn(),
  destroy: vi.fn(),
};

const sharedSpies = {
  mountRichTextEditor: vi.fn(() => mockEditor),
  registerRichTextDocumentPageAI: vi.fn(() => () => {}),
  waitForRichTextEditorOperations: vi.fn(async () => true),
  createSavePageOperation: vi.fn((options: Record<string, unknown>) => options),
  createSimplePageOperation: vi.fn((options: Record<string, unknown>) => options),
  createParameterizedPageOperation: vi.fn(
    (options: Record<string, unknown>) => options,
  ),
  createKeywordSearchPageOperation: vi.fn(
    (options: Record<string, unknown>) => options,
  ),
  createPrefilledCreatePageOperation: vi.fn(
    (options: Record<string, unknown>) => options,
  ),
  createRefreshPageOperation: vi.fn((options: Record<string, unknown>) => options),
  routerPush: vi.fn(),
  downloadBlob: vi.fn(),
};

function setAccessCodes(codes: string[]) {
  accessState.codes = codes;
}

function installSharedApi() {
  (globalThis as unknown as Record<string, unknown>).NovusPluginShared = {
    $t: (key: string) => {
      if (key === 'common.noPermissions') return 'No permissions';
      if (key === 'common.loading') return 'Loading';
      return key.split('.').pop() ?? key;
    },
    getAccessCodes: () => accessState.codes,
    hasAccessByCodes: (codes: string | string[] | undefined) => {
      const requested = Array.isArray(codes)
        ? codes
        : codes
          ? [codes]
          : [];
      if (requested.length === 0) return true;
      if (accessState.codes.includes('*')) return true;
      return requested.some((code) => accessState.codes.includes(code));
    },
    mountRichTextEditor: sharedSpies.mountRichTextEditor,
    registerRichTextDocumentPageAI: sharedSpies.registerRichTextDocumentPageAI,
    waitForRichTextEditorOperations: sharedSpies.waitForRichTextEditorOperations,
    createSavePageOperation: sharedSpies.createSavePageOperation,
    createSimplePageOperation: sharedSpies.createSimplePageOperation,
    createParameterizedPageOperation:
      sharedSpies.createParameterizedPageOperation,
    createKeywordSearchPageOperation:
      sharedSpies.createKeywordSearchPageOperation,
    createPrefilledCreatePageOperation:
      sharedSpies.createPrefilledCreatePageOperation,
    createRefreshPageOperation: sharedSpies.createRefreshPageOperation,
    router: {
      push: sharedSpies.routerPush,
      currentRoute: {
        value: {
          meta: {
            accessCodes: ['plugin.novusdoc.novusdoc_portal:view'],
          },
        },
      },
    },
    downloadBlob: sharedSpies.downloadBlob,
  };
}

async function flushUi(ms = 0) {
  await Promise.resolve();
  if (ms > 0) {
    await new Promise((resolve) => setTimeout(resolve, ms));
  }
  await Promise.resolve();
}

describe('NovusDoc permission bridge', () => {
  beforeEach(() => {
    history.replaceState({}, '', '/tenant/plugins/novusdoc');
    setAccessCodes([]);
    installSharedApi();

    apiMocks.listFolders.mockReset();
    apiMocks.listFolders.mockResolvedValue({
      items: [{ id: 1, name: 'Folder A', parent_id: null, sort_order: 0 }],
      total: 1,
    });
    apiMocks.listDocs.mockReset();
    apiMocks.listDocs.mockResolvedValue({
      items: [
        {
          id: 7,
          title: 'Doc A',
          word_count: 12,
          status: 'draft',
          is_pinned: false,
          folder_id: 1,
          cover_image: null,
          created_at: null,
          updated_at: '2026-04-04T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      size: 20,
    });
    apiMocks.searchDocs.mockReset();
    apiMocks.createDoc.mockReset();
    apiMocks.deleteDoc.mockReset();
    apiMocks.createFolder.mockReset();
    apiMocks.deleteFolder.mockReset();
    apiMocks.getDoc.mockReset();
    apiMocks.getDoc.mockResolvedValue({
      document: {
        id: 42,
        title: 'Read only doc',
        content: { type: 'doc' },
        content_text: 'Sample',
        word_count: 1,
        status: 'draft',
        is_pinned: false,
        folder_id: null,
        cover_image: null,
        created_at: null,
        updated_at: null,
      },
    });
    apiMocks.updateDoc.mockReset();
    apiMocks.updateDoc.mockResolvedValue({ document: {} });
    apiMocks.getExportUrl.mockReset();
    apiMocks.getExportUrl.mockReturnValue('/export');
    apiMocks.exportDocumentAsBlob.mockReset();
    apiMocks.exportDocumentAsBlob.mockResolvedValue(new Blob(['doc']));

    Object.values(sharedSpies).forEach((spy) => spy.mockClear());
  });

  afterEach(() => {
    delete (globalThis as unknown as Record<string, unknown>).NovusPluginShared;
    document.body.innerHTML = '';
  });

  it('blocks list bootstrap when route access is missing', async () => {
    const wrapper = mount(DocumentList, { attachTo: document.body });
    await flushUi();

    expect(apiMocks.listFolders).not.toHaveBeenCalled();
    expect(apiMocks.listDocs).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="novusdoc-no-permission"]').text()).toBe(
      'No permissions',
    );
    expect(wrapper.find('[data-testid="novusdoc-new-doc"]').exists()).toBe(
      false,
    );
  });

  it('keeps list view readable but hides mutating CTAs for view-only access', async () => {
    setAccessCodes(['plugin.novusdoc.novusdoc_portal:view']);

    const wrapper = mount(DocumentList, { attachTo: document.body });
    await flushUi();

    expect(apiMocks.listFolders).toHaveBeenCalledTimes(1);
    expect(apiMocks.listDocs).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="novusdoc-no-permission"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="novusdoc-new-doc"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="novusdoc-new-folder"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="novusdoc-delete-doc"]').exists()).toBe(
      false,
    );
  });

  it('blocks editor bootstrap when route access is missing', async () => {
    const wrapper = mount(DocumentEditor, {
      attachTo: document.body,
      props: { id: '42' },
    });
    await flushUi(80);

    expect(apiMocks.getDoc).not.toHaveBeenCalled();
    expect(sharedSpies.mountRichTextEditor).not.toHaveBeenCalled();
    expect(wrapper.get('[data-testid="novusdoc-no-permission"]').text()).toBe(
      'No permissions',
    );
  });

  it('mounts a read-only editor for view-only access', async () => {
    setAccessCodes(['plugin.novusdoc.novusdoc_portal:view']);

    const wrapper = mount(DocumentEditor, {
      attachTo: document.body,
      props: { id: '42' },
    });
    await flushUi(120);

    expect(apiMocks.getDoc).toHaveBeenCalledWith(42);
    expect(sharedSpies.mountRichTextEditor).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({ editable: false }),
    );
    expect(
      wrapper.get('[data-testid="novusdoc-editor-title"]').attributes(
        'readonly',
      ),
    ).toBeDefined();
    expect(wrapper.find('[data-testid="novusdoc-toggle-status"]').exists()).toBe(
      false,
    );
    expect(wrapper.find('[data-testid="novusdoc-export-menu"]').exists()).toBe(
      false,
    );
  });
});
