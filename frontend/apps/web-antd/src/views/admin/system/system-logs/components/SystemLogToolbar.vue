<script lang="ts" setup>
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Spin } from 'ant-design-vue';

import { $t as t } from '#/locales';

import { useSystemLogsContext } from '../composables/useSystemLogs';

const {
  activeCategoryMeta,
  downloadingFile,
  getCategoryVisual,
  getPillButtonClass,
  logContent,
  onCopyAll,
  onDownload,
  onRefresh,
  selectedFile,
  statsLoading,
  toolbarMetrics,
} = useSystemLogsContext();

const translatedMetrics = computed(() =>
  toolbarMetrics.value.map((metric) => ({
    ...metric,
    label: t(metric.labelKey),
  })),
);

const toolbarChips = computed(() => {
  const chips = [
    {
      key: 'file',
      icon: 'lucide:file-code-2',
      className: 'bg-background/90 text-foreground',
      text:
        selectedFile.value?.filename ??
        t('admin.system.systemLog.noSelectedFile'),
    },
  ];

  if (activeCategoryMeta.value) {
    const categoryVisual = getCategoryVisual(activeCategoryMeta.value.code);

    chips.push({
      key: 'category',
      icon: categoryVisual.icon,
      className: categoryVisual.badge,
      text: `${t('admin.system.systemLog.category')}: ${activeCategoryMeta.value.name}`,
    });
  }

  if (selectedFile.value?.isCurrent) {
    chips.push({
      key: 'live',
      icon: 'lucide:activity',
      className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
      text: t('admin.system.systemLog.running'),
    });
  }

  return chips;
});
</script>

<template>
  <section
    class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm"
  >
    <div
      class="flex flex-col gap-3 2xl:flex-row 2xl:items-center 2xl:justify-between"
    >
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:activity" class="size-4" />
          </span>
          <h1 class="text-base font-semibold text-foreground">
            {{ t('admin.system.systemLog.title') }}
          </h1>
          <span class="hidden text-xs text-muted-foreground xl:inline">
            {{ t('admin.system.systemLog.pageDesc') }}
          </span>
        </div>

        <div class="mt-2 flex flex-wrap gap-2">
          <span
            v-for="chip in toolbarChips"
            :key="chip.key"
            class="inline-flex max-w-full items-center gap-2 rounded-full border border-transparent px-2.5 py-1 text-xs"
            :class="chip.className"
          >
            <IconifyIcon :icon="chip.icon" class="size-3.5 flex-shrink-0" />
            <span class="max-w-[220px] truncate">{{ chip.text }}</span>
          </span>
        </div>
      </div>

      <div class="flex flex-col gap-3 xl:flex-row xl:items-center">
        <Spin :spinning="statsLoading">
          <div class="flex flex-wrap gap-2">
            <span
              v-for="metric in translatedMetrics"
              :key="metric.key"
              class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
            >
              <span class="mr-1 font-semibold text-foreground">{{
                metric.value
              }}</span>
              {{ metric.label }}
            </span>
          </div>
        </Spin>

        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            class="inline-flex h-9 items-center gap-2 rounded-full bg-primary px-3.5 text-[13px] font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            @click="void onRefresh()"
          >
            <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            {{ t('admin.system.systemLog.refresh') }}
          </button>
          <button
            type="button"
            :class="getPillButtonClass()"
            :disabled="
              !selectedFile || downloadingFile === selectedFile.filename
            "
            @click="selectedFile && void onDownload(selectedFile)"
          >
            <IconifyIcon icon="lucide:download" class="size-4" />
            {{ t('admin.system.systemLog.download') }}
          </button>
          <button
            type="button"
            :class="getPillButtonClass()"
            :disabled="!logContent"
            @click="void onCopyAll()"
          >
            <IconifyIcon icon="lucide:copy" class="size-4" />
            {{ t('admin.system.systemLog.copyAll') }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
