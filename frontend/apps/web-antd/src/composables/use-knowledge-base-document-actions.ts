import type { Ref } from 'vue';

import { message, Modal } from 'ant-design-vue';

import { $t } from '#/locales';

interface KnowledgeBaseDocumentActionsOptions {
  createQAPair: (
    kbId: number,
    data: { answer: string; question: string },
  ) => Promise<unknown>;
  createTextDocument: (
    kbId: number,
    data: { content: string; title: string },
  ) => Promise<unknown>;
  deleteTitleKey: string;
  deleteDocument: (kbId: number, docId: number) => Promise<void>;
  kbId: Ref<number>;
  onMutated: () => Promise<void> | void;
  qaBatchImport?: (kbId: number, file: File) => Promise<unknown>;
  reindex: (kbId: number) => Promise<{ document_count: number }>;
  reindexConfirmKey: string;
  reindexStartedKey: string;
  reindexTitleKey: string;
  retryDocument: (kbId: number, docId: number) => Promise<unknown>;
  successMessageKey: string;
  uploadDocument: (kbId: number, file: File) => Promise<unknown>;
  urlImport?: (kbId: number, urls: string[]) => Promise<unknown>;
}

export function useKnowledgeBaseDocumentActions<
  TDoc extends { file_name: string; id: number },
>(options: KnowledgeBaseDocumentActionsOptions) {
  async function handleUploadFile(file: File) {
    await options.uploadDocument(options.kbId.value, file);
  }

  async function handleTextSubmit(data: { content: string; title: string }) {
    await options.createTextDocument(options.kbId.value, data);
  }

  async function handleQASubmit(data: { answer: string; question: string }) {
    await options.createQAPair(options.kbId.value, data);
  }

  async function handleQABatchImport(file: File) {
    if (!options.qaBatchImport) return undefined;
    return await options.qaBatchImport(options.kbId.value, file);
  }

  async function handleUrlImport(urls: string[]) {
    if (!options.urlImport) return undefined;
    return await options.urlImport(options.kbId.value, urls);
  }

  async function handleDocPickerSuccess() {
    await options.onMutated();
  }

  function handleDeleteDoc(doc: TDoc) {
    Modal.confirm({
      title: $t(options.deleteTitleKey),
      content: doc.file_name,
      async onOk() {
        await options.deleteDocument(options.kbId.value, doc.id);
        message.success($t(options.successMessageKey));
        await options.onMutated();
      },
    });
  }

  async function handleRetryDoc(doc: TDoc) {
    try {
      await options.retryDocument(options.kbId.value, doc.id);
      message.success($t(options.successMessageKey));
      await options.onMutated();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  function handleReindex() {
    Modal.confirm({
      title: $t(options.reindexTitleKey),
      content: $t(options.reindexConfirmKey),
      async onOk() {
        const result = await options.reindex(options.kbId.value);
        message.success(
          `${$t(options.reindexStartedKey)} (${result.document_count})`,
        );
        await options.onMutated();
      },
    });
  }

  return {
    handleDeleteDoc,
    handleDocPickerSuccess,
    handleQABatchImport,
    handleQASubmit,
    handleReindex,
    handleRetryDoc,
    handleTextSubmit,
    handleUploadFile,
    handleUrlImport,
  };
}
