<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import { KnowledgeDocumentPicker } from '#/components/business/knowledge-document-picker';
import { $t } from '#/locales';

interface Props {
  canManage?: boolean;
  i18nPrefix: string;
  onQABatchImport?: (file: File) => Promise<unknown>;
  onQASubmit: (data: { answer: string; question: string }) => Promise<unknown>;
  onReindex: () => void;
  onTextSubmit: (data: { content: string; title: string }) => Promise<unknown>;
  onUploadFile: (file: File) => Promise<unknown>;
  onUrlImport?: (urls: string[]) => Promise<unknown>;
  onSuccess: () => void;
  reindexAccessCode?: string;
}

withDefaults(defineProps<Props>(), {
  canManage: true,
  onQABatchImport: undefined,
  onUrlImport: undefined,
  reindexAccessCode: '',
});
</script>

<template>
  <div class="mb-4 flex items-center justify-between">
    <KnowledgeDocumentPicker
      v-if="canManage"
      :upload-fn="onUploadFile"
      :text-fn="onTextSubmit"
      :qa-fn="onQASubmit"
      :qa-batch-fn="onQABatchImport"
      :url-fn="onUrlImport"
      @success="onSuccess"
    />
    <Button
      v-if="canManage"
      v-access:code="reindexAccessCode ? [reindexAccessCode] : undefined"
      @click="onReindex"
    >
      <template #icon>
        <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
      </template>
      {{ $t(`${i18nPrefix}.reindex.title`) }}
    </Button>
  </div>
</template>
