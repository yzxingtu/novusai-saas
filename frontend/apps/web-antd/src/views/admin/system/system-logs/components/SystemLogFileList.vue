<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Empty, Input, Popconfirm, Spin, Tooltip } from 'ant-design-vue';

import { $t as t } from '#/locales';
import { formatDate } from '#/utils/common';

import { useSystemLogsContext } from '../composables/useSystemLogs';

const {
  activeCategoryMeta,
  downloadingFile,
  fileSearchQuery,
  files,
  filesLoading,
  filteredFiles,
  getIconButtonClass,
  onDelete,
  onDownload,
  onSelectFile,
  selectedFile,
} = useSystemLogsContext();

const summaryText = computed(
  () => `${filteredFiles.value.length} / ${files.value.length}`,
);
</script>

<template>
  <aside
    class="flex min-h-[320px] min-w-0 flex-col overflow-hidden rounded-[20px] border border-border/70 bg-card shadow-sm"
  >
    <div class="border-b border-border/60 px-4 py-3">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="text-sm font-semibold text-foreground">
            {{ t('admin.system.systemLog.files') }}
          </div>
          <p class="mt-1 line-clamp-1 text-xs text-muted-foreground">
            {{
              activeCategoryMeta?.description ||
              t('admin.system.systemLog.filesDesc')
            }}
          </p>
        </div>
        <span class="shrink-0 text-xs text-muted-foreground">{{
          summaryText
        }}</span>
      </div>

      <div class="mt-3">
        <Input
          v-model:value="fileSearchQuery"
          :placeholder="t('admin.system.systemLog.searchFiles')"
          allow-clear
          size="small"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="text-muted-foreground" />
          </template>
        </Input>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-auto p-2">
      <div v-if="filesLoading" class="space-y-2">
        <div
          v-for="item in 5"
          :key="item"
          class="rounded-xl border border-border/60 bg-background/80 p-3"
        >
          <Spin />
        </div>
      </div>

      <div v-else-if="filteredFiles.length > 0" class="space-y-2">
        <article
          v-for="file in filteredFiles"
          :key="file.filename"
          class="cursor-pointer rounded-xl border px-3 py-2.5 transition-all"
          :class="
            selectedFile?.filename === file.filename
              ? 'border-primary/25 bg-primary/5 shadow-sm'
              : 'border-border/60 bg-background/80 hover:border-primary/20 hover:bg-accent/40'
          "
          @click="onSelectFile(file)"
        >
          <div class="flex items-start gap-3">
            <span
              class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"
            >
              <IconifyIcon icon="lucide:file-code-2" class="size-3.5" />
            </span>

            <div class="min-w-0 flex-1">
              <div class="flex items-start justify-between gap-2">
                <Tooltip :title="file.filename">
                  <div class="truncate text-sm font-medium text-foreground">
                    {{ file.filename }}
                  </div>
                </Tooltip>

                <div class="flex shrink-0 items-center gap-1">
                  <Tooltip :title="t('admin.system.systemLog.download')">
                    <button
                      type="button"
                      :class="getIconButtonClass()"
                      :disabled="downloadingFile === file.filename"
                      @click.stop="void onDownload(file)"
                    >
                      <Spin
                        v-if="downloadingFile === file.filename"
                        size="small"
                      />
                      <IconifyIcon
                        v-else
                        icon="lucide:download"
                        class="size-3.5"
                      />
                    </button>
                  </Tooltip>

                  <Popconfirm
                    v-if="!file.isCurrent"
                    :title="
                      t('admin.system.systemLog.messages.deleteConfirm', {
                        name: file.filename,
                      })
                    "
                    @confirm="void onDelete(file)"
                  >
                    <button
                      type="button"
                      :class="getIconButtonClass(true)"
                      @click.stop
                    >
                      <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                    </button>
                  </Popconfirm>
                </div>
              </div>

              <div
                class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground"
              >
                <span>{{ file.sizeFormatted }}</span>
                <span>{{ formatDate(file.modifiedAt, 'MM-DD HH:mm') }}</span>
                <span
                  v-if="file.isCurrent"
                  class="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-200"
                >
                  {{ t('admin.system.systemLog.running') }}
                </span>
                <span
                  v-if="selectedFile?.filename === file.filename"
                  class="rounded-full bg-primary/10 px-1.5 py-0.5 text-primary"
                >
                  {{ t('admin.system.systemLog.current') }}
                </span>
              </div>
            </div>
          </div>
        </article>
      </div>

      <div v-else class="flex h-full items-center justify-center">
        <Empty
          :description="
            fileSearchQuery
              ? t('admin.system.systemLog.emptySearch')
              : t('admin.system.systemLog.noFiles')
          "
        />
      </div>
    </div>
  </aside>
</template>
