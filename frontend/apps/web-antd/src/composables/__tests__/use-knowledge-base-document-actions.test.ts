import { ref } from 'vue';

import { describe, expect, it, vi } from 'vitest';

import { useKnowledgeBaseDocumentActions } from '../use-knowledge-base-document-actions';

const mockRefs = vi.hoisted(() => ({
  confirm: vi.fn(),
  messageSuccess: vi.fn(),
}));

vi.mock('ant-design-vue', () => ({
  Modal: {
    confirm: mockRefs.confirm,
  },
  message: {
    success: mockRefs.messageSuccess,
  },
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

describe('useKnowledgeBaseDocumentActions', () => {
  it('runs delete and reindex flows through injected APIs', async () => {
    const onMutated = vi.fn();
    const actions = useKnowledgeBaseDocumentActions({
      kbId: ref(9),
      uploadDocument: vi.fn(),
      createTextDocument: vi.fn(),
      createQAPair: vi.fn(),
      deleteTitleKey: 'tenant.knowledgeBase.document.delete',
      deleteDocument: vi.fn().mockResolvedValue(undefined),
      retryDocument: vi.fn(),
      reindex: vi.fn().mockResolvedValue({ document_count: 3 }),
      successMessageKey: 'common.operationSuccess',
      reindexTitleKey: 'tenant.knowledgeBase.reindex.title',
      reindexConfirmKey: 'tenant.knowledgeBase.reindex.confirm',
      reindexStartedKey: 'tenant.knowledgeBase.reindex.started',
      onMutated,
    });

    actions.handleDeleteDoc({ id: 1, file_name: 'doc.pdf' });
    await mockRefs.confirm.mock.calls.at(-1)?.[0]?.onOk();

    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'common.operationSuccess',
    );
    expect(onMutated).toHaveBeenCalled();

    actions.handleReindex();
    await mockRefs.confirm.mock.calls.at(-1)?.[0]?.onOk();

    expect(mockRefs.messageSuccess).toHaveBeenCalledWith(
      'tenant.knowledgeBase.reindex.started (3)',
    );
  });
});
