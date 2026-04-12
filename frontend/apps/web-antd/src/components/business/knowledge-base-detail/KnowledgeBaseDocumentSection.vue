<script lang="ts" setup>
import type { KnowledgeBaseDocProgressInfo } from '#/composables/use-knowledge-base-detail-tools';
import type { KnowledgeBaseDocumentRow } from './types';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Pagination,
  Progress,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import {
  getKnowledgeBaseDocStatusColor,
  getKnowledgeBaseDocStatusText,
  getKnowledgeBaseFileIcon,
  getKnowledgeBaseFileIconBg,
  getKnowledgeBaseFileIconColor,
} from '#/composables/use-knowledge-base-detail-tools';
import { formatDate } from '#/utils/common';
import { formatFileSize } from '#/utils/file';

interface Props {
  canDelete?: boolean;
  canRetry?: boolean;
  currentPage?: number;
  documents: KnowledgeBaseDocumentRow[];
  emptyText: string;
  i18nPrefix: string;
  loading: boolean;
  pageSize?: number;
  progressMap: Record<number, KnowledgeBaseDocProgressInfo>;
  total: number;
}

withDefaults(defineProps<Props>(), {
  canDelete: true,
  canRetry: true,
  currentPage: 1,
  pageSize: 20,
});

const emit = defineEmits<{
  delete: [doc: KnowledgeBaseDocumentRow];
  openChunks: [doc: KnowledgeBaseDocumentRow];
  pageChange: [page: number];
  retry: [doc: KnowledgeBaseDocumentRow];
}>();
</script>

<template>
  <Spin :spinning="loading">
    <div
      v-if="documents.length === 0 && !loading"
      class="flex flex-col items-center justify-center py-16"
    >
      <div
        class="mb-3 flex size-14 items-center justify-center rounded-2xl bg-muted"
      >
        <IconifyIcon
          icon="lucide:file-text"
          class="size-7 text-muted-foreground"
        />
      </div>
      <p class="text-sm text-muted-foreground">
        {{ emptyText }}
      </p>
    </div>
    <div v-else class="space-y-2">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="group flex items-center gap-4 rounded-lg border border-border/60 p-3.5 transition-colors hover:border-border hover:bg-accent/30"
      >
        <div
          class="flex size-10 shrink-0 items-center justify-center rounded-lg"
          :class="getKnowledgeBaseFileIconBg(doc.file_type)"
        >
          <IconifyIcon
            :icon="getKnowledgeBaseFileIcon(doc.file_type)"
            class="size-5"
            :class="getKnowledgeBaseFileIconColor(doc.file_type)"
          />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="truncate text-sm font-medium text-foreground">
              {{ doc.file_name }}
            </span>
            <Tag
              :color="getKnowledgeBaseDocStatusColor(doc.status)"
              class="shrink-0"
              style="margin: 0"
            >
              {{ getKnowledgeBaseDocStatusText(i18nPrefix, doc.status) }}
            </Tag>
          </div>
          <div
            class="mt-1 flex items-center gap-3 text-xs text-muted-foreground"
          >
            <span class="inline-flex items-center gap-1">
              <IconifyIcon icon="lucide:file" class="size-3" />
              {{ (doc.file_type || '-').toUpperCase() }}
            </span>
            <span class="inline-flex items-center gap-1">
              <IconifyIcon icon="lucide:hard-drive" class="size-3" />
              {{ formatFileSize(doc.file_size) }}
            </span>
            <span class="inline-flex items-center gap-1">
              <IconifyIcon icon="lucide:puzzle" class="size-3" />
              {{ doc.chunk_count }}
            </span>
            <span class="inline-flex items-center gap-1">
              <IconifyIcon icon="lucide:clock" class="size-3" />
              {{ formatDate(doc.created_at) }}
            </span>
          </div>
          <Progress
            v-if="!['completed', 'error', 'pending'].includes(doc.status)"
            :percent="progressMap[doc.id]?.progress ?? 0"
            size="small"
            :show-info="false"
            :stroke-color="{
              from: 'hsl(var(--primary))',
              to: 'hsl(var(--success))',
            }"
            class="!mb-0 !mt-1.5 max-w-xs"
          />
          <Tooltip
            v-if="doc.error_message"
            :title="doc.error_message"
            :overlay-style="{ maxWidth: '400px' }"
          >
            <span
              class="mt-0.5 inline-block cursor-help truncate text-xs text-destructive"
            >
              {{ doc.error_message }}
            </span>
          </Tooltip>
        </div>
        <div
          class="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100"
        >
          <Tooltip
            v-if="doc.status === 'completed'"
            :title="$t(`${i18nPrefix}.document.viewChunks`)"
          >
            <Button
              type="text"
              size="small"
              class="!size-8 !min-w-0 !p-0"
              @click="emit('openChunks', doc)"
            >
              <IconifyIcon
                icon="lucide:layers"
                class="size-4 text-muted-foreground hover:text-primary"
              />
            </Button>
          </Tooltip>
          <Tooltip
            v-if="canRetry && doc.status === 'error'"
            :title="$t(`${i18nPrefix}.document.retry`)"
          >
            <Button
              type="text"
              size="small"
              class="!size-8 !min-w-0 !p-0"
              @click="emit('retry', doc)"
            >
              <IconifyIcon
                icon="lucide:rotate-cw"
                class="size-4 text-muted-foreground hover:text-warning"
              />
            </Button>
          </Tooltip>
          <Tooltip
            v-if="canDelete"
            :title="$t(`${i18nPrefix}.document.delete`)"
          >
            <Button
              type="text"
              size="small"
              danger
              class="!size-8 !min-w-0 !p-0"
              @click="emit('delete', doc)"
            >
              <IconifyIcon icon="lucide:trash-2" class="size-4" />
            </Button>
          </Tooltip>
        </div>
      </div>
    </div>
    <div v-if="total > pageSize" class="mt-4 flex justify-end">
      <Pagination
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        size="small"
        :show-size-changer="false"
        @change="(page) => emit('pageChange', page)"
      />
    </div>
  </Spin>
</template>
