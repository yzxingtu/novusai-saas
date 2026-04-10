<script lang="ts" setup>
import type { ComponentPublicInstance } from 'vue';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Input, Spin, Tag, Tooltip } from 'ant-design-vue';

import { $t as t } from '#/locales';
import { formatDate } from '#/utils/common';

import { useSystemLogsContext } from '../composables/useSystemLogs';

const {
  activeCategoryMeta,
  autoScroll,
  contentLoading,
  contentSearchQuery,
  displayedLineCount,
  getContentClass,
  getLevelBadgeClass,
  getLineNumber,
  getPillButtonClass,
  isDarkTheme,
  lineHoverClass,
  lineMatchClass,
  logContainerRef,
  logContent,
  matchedLineCount,
  onCopyLine,
  onLoadMore,
  onRefreshCurrent,
  readerShellClass,
  readerStatusBarClass,
  renderedLines,
  scrollReaderToTop,
  selectedFile,
} = useSystemLogsContext();

function isComponentWithElement(
  value: ComponentPublicInstance | Element | null,
): value is ComponentPublicInstance & { $el: Element } {
  return !!value && typeof value === 'object' && '$el' in value;
}

function setLogContainerRef(element: ComponentPublicInstance | Element | null) {
  if (element instanceof HTMLDivElement) {
    logContainerRef.value = element;
    return;
  }
  if (
    isComponentWithElement(element) &&
    element.$el instanceof HTMLDivElement
  ) {
    logContainerRef.value = element.$el;
    return;
  }
  logContainerRef.value = null;
}

const metaChips = computed(() => {
  const chips: Array<{ key: string; text: string }> = [];

  if (activeCategoryMeta.value) {
    chips.push({
      key: 'category',
      text: `${t('admin.system.systemLog.category')}: ${activeCategoryMeta.value.name}`,
    });
  }

  if (selectedFile.value) {
    chips.push(
      {
        key: 'size',
        text: `${t('admin.system.systemLog.size')}: ${selectedFile.value.sizeFormatted}`,
      },
      {
        key: 'modified',
        text: `${t('admin.system.systemLog.modifiedAt')}: ${formatDate(
          selectedFile.value.modifiedAt,
          'YYYY-MM-DD HH:mm',
        )}`,
      },
    );
  }

  if (logContent.value) {
    chips.push({
      key: 'total-lines',
      text: `${t('admin.system.systemLog.totalLines')}: ${logContent.value.totalLines}`,
    });
  }

  if (contentSearchQuery.value.trim()) {
    chips.push({
      key: 'matches',
      text: `${t('admin.system.systemLog.matches')}: ${matchedLineCount.value}`,
    });
  }

  return chips;
});
</script>

<template>
  <section
    class="flex min-h-[620px] min-w-0 flex-col overflow-hidden rounded-[20px] border border-border/70 bg-card shadow-sm"
  >
    <div class="border-b border-border/60 px-4 py-3">
      <div
        class="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between"
      >
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <Tooltip :title="selectedFile?.filename">
              <h2
                class="max-w-full truncate text-base font-semibold text-foreground"
              >
                {{
                  selectedFile?.filename ||
                  t('admin.system.systemLog.noSelectedFile')
                }}
              </h2>
            </Tooltip>
            <Tag
              v-if="selectedFile?.isCurrent"
              color="success"
              class="!mr-0 rounded-full"
            >
              {{ t('admin.system.systemLog.running') }}
            </Tag>
          </div>

          <div class="mt-2 flex flex-wrap gap-2">
            <span
              v-for="chip in metaChips"
              :key="chip.key"
              class="rounded-full border border-border/60 bg-background/80 px-2.5 py-1 text-[11px] text-muted-foreground"
            >
              {{ chip.text }}
            </span>
          </div>
        </div>

        <div class="flex flex-col gap-2 xl:flex-row xl:items-center">
          <div class="min-w-[220px] xl:w-[280px]">
            <Input
              v-model:value="contentSearchQuery"
              :placeholder="t('admin.system.systemLog.searchContent')"
              allow-clear
              size="small"
            >
              <template #prefix>
                <IconifyIcon
                  icon="lucide:search"
                  class="text-muted-foreground"
                />
              </template>
            </Input>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              :class="getPillButtonClass()"
              @click="void onRefreshCurrent()"
            >
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
              {{ t('admin.system.systemLog.refresh') }}
            </button>
            <button
              type="button"
              :class="getPillButtonClass(autoScroll)"
              @click="autoScroll = !autoScroll"
            >
              <IconifyIcon icon="lucide:arrow-up-to-line" class="size-4" />
              {{ t('admin.system.systemLog.autoScroll') }}
            </button>
            <button
              type="button"
              :class="getPillButtonClass(isDarkTheme)"
              @click="isDarkTheme = !isDarkTheme"
            >
              <IconifyIcon
                :icon="isDarkTheme ? 'lucide:sun' : 'lucide:moon'"
                class="size-4"
              />
              {{
                isDarkTheme
                  ? t('admin.system.systemLog.lightTheme')
                  : t('admin.system.systemLog.darkTheme')
              }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="flex min-h-0 flex-1 flex-col p-3">
      <div
        class="relative min-h-[460px] flex-1 overflow-hidden rounded-[18px] border"
        :class="readerShellClass"
      >
        <div
          :ref="setLogContainerRef"
          class="scrollbar-thin relative h-full overflow-auto"
        >
          <Spin :spinning="contentLoading" wrapper-class-name="h-full">
            <template v-if="logContent && selectedFile">
              <div class="min-w-[680px] p-3 font-mono text-xs leading-6 sm:p-4">
                <div
                  v-for="(line, index) in renderedLines"
                  :key="`${selectedFile.filename}-${index}`"
                  class="group relative grid grid-cols-[52px_minmax(0,1fr)] gap-3 rounded-lg border border-transparent px-2 py-1 transition-all"
                  :class="[lineHoverClass, line.isMatch ? lineMatchClass : '']"
                >
                  <div
                    class="select-none pt-0.5 text-right text-[11px]"
                    :class="isDarkTheme ? 'text-slate-500' : 'text-slate-400'"
                  >
                    {{ getLineNumber(index) }}
                  </div>

                  <div class="relative min-w-0">
                    <template v-if="line.timestamp">
                      <div class="flex min-w-0 items-start gap-2.5">
                        <span
                          class="shrink-0 pt-0.5 text-[11px]"
                          :class="
                            isDarkTheme ? 'text-slate-500' : 'text-slate-400'
                          "
                        >
                          {{ line.timestamp }}
                        </span>
                        <span
                          class="flex w-14 shrink-0 items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold"
                          :class="getLevelBadgeClass(line.level)"
                        >
                          {{ line.level }}
                        </span>
                        <span
                          class="min-w-0 whitespace-pre-wrap break-all transition-colors"
                          :class="getContentClass(line)"
                        >
                          {{ line.content }}
                        </span>
                      </div>
                    </template>
                    <template v-else>
                      <span
                        class="whitespace-pre-wrap break-all transition-colors"
                        :class="getContentClass(line)"
                      >
                        {{ line.content }}
                      </span>
                    </template>
                  </div>

                  <div
                    class="absolute right-2 top-1/2 hidden -translate-y-1/2 group-hover:flex"
                  >
                    <Tooltip :title="t('admin.system.systemLog.copyLine')">
                      <button
                        type="button"
                        class="flex size-6 items-center justify-center rounded-full border border-border/60 bg-background/90 text-muted-foreground shadow-sm transition-colors hover:border-primary/20 hover:text-primary"
                        @click.stop="void onCopyLine(line.originalLine)"
                      >
                        <IconifyIcon icon="lucide:copy" class="size-3" />
                      </button>
                    </Tooltip>
                  </div>
                </div>

                <div class="mt-5 flex justify-center pb-1">
                  <Button
                    v-if="logContent.hasMore"
                    type="dashed"
                    :loading="contentLoading"
                    @click="onLoadMore"
                  >
                    {{ t('admin.system.systemLog.loadMore') }}
                  </Button>
                  <span
                    v-else
                    class="text-xs"
                    :class="isDarkTheme ? 'text-slate-500' : 'text-slate-400'"
                  >
                    --- {{ t('admin.system.systemLog.endOfLog') }} ---
                  </span>
                </div>
              </div>
            </template>

            <div
              v-else
              class="flex h-full flex-col items-center justify-center px-6 text-center"
            >
              <IconifyIcon
                icon="lucide:file-code-2"
                class="size-10"
                :class="isDarkTheme ? 'text-slate-600' : 'text-slate-300'"
              />
              <h3 class="mt-3 text-base font-semibold text-foreground">
                {{ t('admin.system.systemLog.noSelectedFile') }}
              </h3>
              <p class="mt-1 max-w-md text-sm text-muted-foreground">
                {{ t('admin.system.systemLog.selectFileTip') }}
              </p>
            </div>
          </Spin>
        </div>
      </div>

      <div
        class="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-[16px] border px-3 py-2 text-xs"
        :class="readerStatusBarClass"
      >
        <div class="flex flex-wrap gap-4">
          <span>
            {{ t('admin.system.systemLog.lines') }}:
            {{ displayedLineCount }}
          </span>
          <span>
            {{ t('admin.system.systemLog.totalLines') }}:
            {{ logContent?.totalLines ?? 0 }}
          </span>
          <span v-if="contentSearchQuery.trim()">
            {{ t('admin.system.systemLog.matches') }}:
            {{ matchedLineCount }}
          </span>
        </div>

        <div class="flex flex-wrap gap-4">
          <span>{{ selectedFile?.sizeFormatted ?? '-' }}</span>
          <span>UTF-8</span>
          <button
            type="button"
            class="font-medium transition-colors hover:text-primary"
            @click="scrollReaderToTop()"
          >
            {{ t('admin.system.systemLog.backToTop') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
