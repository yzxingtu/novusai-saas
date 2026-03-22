<script lang="ts" setup>
import type { adminApi } from '#/api';
import { computed, nextTick, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Empty,
  Input,
  message,
  Popconfirm,
  Skeleton,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import {
  usePageAIAnchor,
  usePageAIOperations,
} from '#/composables/use-page-ai-registration';
import {
  createKeywordSearchPageOperation,
  createRefreshPageOperation,
} from '#/composables/use-page-ai-operation-helpers';
import { $t } from '#/locales';
import { copyToClipboard, formatDate } from '#/utils/common';

defineOptions({ name: 'SystemLogList' });

type SystemLogCategory = adminApi.SystemLogCategory;
type SystemLogContent = adminApi.SystemLogContent;
type SystemLogFile = adminApi.SystemLogFile;
type SystemLogStats = adminApi.SystemLogStats;

interface CategoryVisual {
  activeCard: string;
  badge: string;
  icon: string;
  iconWrap: string;
}

interface RenderedLogLine {
  content: string;
  isMatch: boolean;
  isStackTrace: boolean;
  level: string;
  originalLine: string;
  timestamp: string;
}

const LOG_PAGE_SIZE = 120;

const DEFAULT_CATEGORY_VISUAL: CategoryVisual = {
  icon: 'lucide:file-code-2',
  iconWrap: 'bg-primary/10 text-primary',
  activeCard: 'border-primary/25 bg-primary/10',
  badge: 'bg-primary/10 text-primary',
};

const CATEGORY_VISUALS: Record<string, CategoryVisual> = {
  app: {
    icon: 'lucide:activity',
    iconWrap: 'bg-sky-500/10 text-sky-600 dark:text-sky-300',
    activeCard: 'border-sky-500/25 bg-sky-500/10',
    badge: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
  },
  error: {
    icon: 'lucide:triangle-alert',
    iconWrap: 'bg-rose-500/10 text-rose-600 dark:text-rose-300',
    activeCard: 'border-rose-500/25 bg-rose-500/10',
    badge: 'bg-rose-500/10 text-rose-700 dark:text-rose-200',
  },
  db: {
    icon: 'lucide:database',
    iconWrap: 'bg-violet-500/10 text-violet-600 dark:text-violet-300',
    activeCard: 'border-violet-500/25 bg-violet-500/10',
    badge: 'bg-violet-500/10 text-violet-700 dark:text-violet-200',
  },
  task: {
    icon: 'lucide:cpu',
    iconWrap: 'bg-amber-500/10 text-amber-600 dark:text-amber-300',
    activeCard: 'border-amber-500/25 bg-amber-500/10',
    badge: 'bg-amber-500/10 text-amber-700 dark:text-amber-200',
  },
  queue: {
    icon: 'lucide:workflow',
    iconWrap: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-300',
    activeCard: 'border-cyan-500/25 bg-cyan-500/10',
    badge: 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-200',
  },
  captcha: {
    icon: 'lucide:shield-check',
    iconWrap: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-300',
    activeCard: 'border-emerald-500/25 bg-emerald-500/10',
    badge: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
  },
  storage: {
    icon: 'lucide:hard-drive',
    iconWrap: 'bg-blue-500/10 text-blue-600 dark:text-blue-300',
    activeCard: 'border-blue-500/25 bg-blue-500/10',
    badge: 'bg-blue-500/10 text-blue-700 dark:text-blue-200',
  },
  auth: {
    icon: 'lucide:key-round',
    iconWrap: 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-300',
    activeCard: 'border-indigo-500/25 bg-indigo-500/10',
    badge: 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-200',
  },
  impersonate: {
    icon: 'lucide:user-check',
    iconWrap: 'bg-orange-500/10 text-orange-600 dark:text-orange-300',
    activeCard: 'border-orange-500/25 bg-orange-500/10',
    badge: 'bg-orange-500/10 text-orange-700 dark:text-orange-200',
  },
};

const loading = ref(false);
const filesLoading = ref(false);
const statsLoading = ref(false);
const contentLoading = ref(false);
const downloadingFile = ref<null | string>(null);

const stats = ref<null | SystemLogStats>(null);
const categories = ref<SystemLogCategory[]>([]);
const files = ref<SystemLogFile[]>([]);
const activeCategory = ref('');
const selectedFile = ref<null | SystemLogFile>(null);
const logContent = ref<null | SystemLogContent>(null);

const fileSearchQuery = ref('');
const contentSearchQuery = ref('');
const autoScroll = ref(true);
const isDarkTheme = ref(true);
const logContainerRef = ref<HTMLDivElement | null>(null);

const activeCategoryMeta = computed(() => {
  return (
    categories.value.find(
      (category) => category.code === activeCategory.value,
    ) ?? null
  );
});

const filteredFiles = computed(() => {
  const query = fileSearchQuery.value.trim().toLowerCase();
  if (!query) return files.value;
  return files.value.filter((file) =>
    file.filename.toLowerCase().includes(query),
  );
});

const renderedLines = computed<RenderedLogLine[]>(() => {
  if (!logContent.value) return [];
  const query = contentSearchQuery.value.trim().toLowerCase();

  return logContent.value.lines.map((line) => {
    const parsed = parseLogLine(line);
    return {
      ...parsed,
      originalLine: line,
      isMatch: query.length > 0 && line.toLowerCase().includes(query),
    };
  });
});

const matchedLineCount = computed(() => {
  return renderedLines.value.reduce((total, line) => {
    return total + (line.isMatch ? 1 : 0);
  }, 0);
});

const displayedLineCount = computed(() => logContent.value?.lines.length ?? 0);

const toolbarMetrics = computed(() => {
  return [
    {
      key: 'total-files',
      label: $t('admin.system.systemLog.totalFiles'),
      value: String(stats.value?.totalFiles ?? 0),
    },
    {
      key: 'total-size',
      label: $t('admin.system.systemLog.totalSize'),
      value: stats.value?.totalSizeFormatted ?? '-',
    },
    {
      key: 'categories',
      label: $t('admin.system.systemLog.categories'),
      value: String(categories.value.length),
    },
  ];
});

const toolbarChips = computed(() => {
  const categoryVisual = getCategoryVisual(activeCategoryMeta.value?.code);
  const chips = [
    {
      key: 'category',
      icon: categoryVisual.icon,
      className: categoryVisual.badge,
      text: `${$t('admin.system.systemLog.category')}: ${activeCategoryMeta.value?.name ?? '-'}`,
    },
    {
      key: 'file',
      icon: 'lucide:file-code-2',
      className: 'bg-background/90 text-foreground',
      text:
        selectedFile.value?.filename ??
        $t('admin.system.systemLog.noSelectedFile'),
    },
  ];

  if (selectedFile.value?.isCurrent) {
    chips.push({
      key: 'live',
      icon: 'lucide:activity',
      className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
      text: $t('admin.system.systemLog.running'),
    });
  }

  return chips;
});

const readerMetaChips = computed(() => {
  const chips: Array<{ key: string; text: string }> = [];

  if (activeCategoryMeta.value) {
    chips.push({
      key: 'category',
      text: `${$t('admin.system.systemLog.category')}: ${activeCategoryMeta.value.name}`,
    });
  }

  if (selectedFile.value) {
    chips.push({
      key: 'size',
      text: `${$t('admin.system.systemLog.size')}: ${selectedFile.value.sizeFormatted}`,
    });
    chips.push({
      key: 'modified',
      text: `${$t('admin.system.systemLog.modifiedAt')}: ${formatDate(selectedFile.value.modifiedAt, 'YYYY-MM-DD HH:mm')}`,
    });
  }

  if (logContent.value) {
    chips.push({
      key: 'total-lines',
      text: `${$t('admin.system.systemLog.totalLines')}: ${logContent.value.totalLines}`,
    });
  }

  if (contentSearchQuery.value.trim()) {
    chips.push({
      key: 'matches',
      text: `${$t('admin.system.systemLog.matches')}: ${matchedLineCount.value}`,
    });
  }

  return chips;
});

const readerShellClass = computed(() => {
  return isDarkTheme.value
    ? 'border-slate-900 bg-slate-950 text-slate-100'
    : 'border-stone-200 bg-white text-slate-800';
});

const readerStatusBarClass = computed(() => {
  return isDarkTheme.value
    ? 'border-slate-800/80 bg-slate-900/70 text-slate-400'
    : 'border-border/60 bg-background/80 text-muted-foreground';
});

const lineHoverClass = computed(() => {
  return isDarkTheme.value ? 'hover:bg-white/5' : 'hover:bg-primary/5';
});

const lineMatchClass = computed(() => {
  return isDarkTheme.value
    ? 'border-amber-300/30 bg-amber-400/10'
    : 'border-amber-200 bg-amber-50';
});

function getCategoryVisual(code: string | undefined): CategoryVisual {
  if (!code) return DEFAULT_CATEGORY_VISUAL;
  return CATEGORY_VISUALS[code] ?? DEFAULT_CATEGORY_VISUAL;
}

function getPillButtonClass(active = false): string {
  return [
    'inline-flex h-9 items-center gap-2 rounded-full border px-3.5 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
    active
      ? 'border-primary/25 bg-primary/10 text-primary'
      : 'border-border/60 bg-background/85 text-foreground hover:border-primary/20 hover:text-primary',
  ].join(' ');
}

function getIconButtonClass(danger = false): string {
  return [
    'inline-flex size-7 items-center justify-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-50',
    danger
      ? 'border-red-200 bg-red-50 text-red-600 hover:border-red-300 hover:bg-red-100 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300'
      : 'border-border/60 bg-background/90 text-muted-foreground hover:border-primary/20 hover:text-primary',
  ].join(' ');
}

function parseLogLine(
  line: string,
): Omit<RenderedLogLine, 'isMatch' | 'originalLine'> {
  const parts = line.split('|');
  if (parts.length >= 3) {
    const timestamp = (parts[0] ?? '').trim();
    const level = (parts[1] ?? '').trim().toUpperCase();
    const content = parts.slice(2).join('|').trim();
    const isValidTimestamp = /^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$/.test(
      timestamp,
    );

    if (isValidTimestamp) {
      return {
        timestamp,
        level,
        content,
        isStackTrace: false,
      };
    }
  }

  return {
    timestamp: '',
    level: '',
    content: line,
    isStackTrace:
      line.startsWith('  ') ||
      line.startsWith('\t') ||
      line.includes('File "') ||
      line.includes('Traceback'),
  };
}

function getLevelBadgeClass(level: string): string {
  switch (level) {
    case 'CRITICAL':
    case 'ERROR':
    case 'FATAL': {
      return isDarkTheme.value
        ? 'border border-red-500/30 bg-red-500/15 text-red-300'
        : 'border border-red-200 bg-red-50 text-red-600';
    }
    case 'DEBUG': {
      return isDarkTheme.value
        ? 'border border-violet-500/30 bg-violet-500/15 text-violet-300'
        : 'border border-violet-200 bg-violet-50 text-violet-600';
    }
    case 'INFO': {
      return isDarkTheme.value
        ? 'border border-sky-500/30 bg-sky-500/15 text-sky-300'
        : 'border border-sky-200 bg-sky-50 text-sky-600';
    }
    case 'SUCCESS': {
      return isDarkTheme.value
        ? 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
        : 'border border-emerald-200 bg-emerald-50 text-emerald-600';
    }
    case 'WARN':
    case 'WARNING': {
      return isDarkTheme.value
        ? 'border border-amber-500/30 bg-amber-500/15 text-amber-300'
        : 'border border-amber-200 bg-amber-50 text-amber-600';
    }
    default: {
      return isDarkTheme.value
        ? 'border border-slate-500/30 bg-slate-500/15 text-slate-300'
        : 'border border-slate-200 bg-slate-100 text-slate-600';
    }
  }
}

function getContentClass(line: RenderedLogLine): string {
  if (line.isStackTrace) {
    return isDarkTheme.value
      ? 'font-mono italic text-rose-200/85'
      : 'font-mono italic text-rose-600';
  }

  if (!isDarkTheme.value) {
    switch (line.level) {
      case 'DEBUG': {
        return 'text-violet-700';
      }
      case 'ERROR': {
        return 'text-red-700';
      }
      case 'INFO': {
        return 'text-sky-700';
      }
      case 'SUCCESS': {
        return 'text-emerald-700';
      }
      case 'WARN':
      case 'WARNING': {
        return 'text-amber-700';
      }
      default: {
        return 'text-slate-700';
      }
    }
  }

  switch (line.level) {
    case 'DEBUG': {
      return 'text-violet-200';
    }
    case 'ERROR': {
      return 'text-red-200';
    }
    case 'INFO': {
      return 'text-sky-100';
    }
    case 'SUCCESS': {
      return 'text-emerald-200';
    }
    case 'WARN':
    case 'WARNING': {
      return 'text-amber-100';
    }
    default: {
      return 'text-slate-200';
    }
  }
}

function getLineNumber(index: number): number {
  if (!logContent.value) return index + 1;
  return index + 1 + (logContent.value.page - 1) * logContent.value.pageSize;
}

function scrollReaderToTop() {
  logContainerRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
}

async function loadStats() {
  statsLoading.value = true;
  try {
    stats.value = await admin.getSystemLogStatsApi();
  } catch {
    stats.value = null;
  } finally {
    statsLoading.value = false;
  }
}

async function loadCategories(): Promise<void> {
  loading.value = true;
  try {
    const result = await admin.getSystemLogCategoriesApi();
    categories.value = result;

    const nextActive = result.some(
      (category) => category.code === activeCategory.value,
    )
      ? activeCategory.value
      : (result[0]?.code ?? '');

    if (!nextActive) {
      activeCategory.value = '';
      files.value = [];
      selectedFile.value = null;
      logContent.value = null;
      return;
    }

    activeCategory.value = nextActive;
  } catch {
    categories.value = [];
    activeCategory.value = '';
    files.value = [];
    selectedFile.value = null;
    logContent.value = null;
  } finally {
    loading.value = false;
  }
}

async function loadFiles() {
  if (!activeCategory.value) {
    files.value = [];
    selectedFile.value = null;
    logContent.value = null;
    return;
  }

  const previousSelectedFilename = selectedFile.value?.filename ?? null;

  filesLoading.value = true;
  try {
    const result = await admin.getSystemLogFilesApi({
      category: activeCategory.value,
    });
    files.value = result;

    const nextSelected =
      result.find((file) => file.filename === previousSelectedFilename) ??
      result[0] ??
      null;

    selectedFile.value = nextSelected;

    if (nextSelected) {
      await loadContent(nextSelected);
    } else {
      logContent.value = null;
    }
  } catch {
    files.value = [];
    selectedFile.value = null;
    logContent.value = null;
  } finally {
    filesLoading.value = false;
  }
}

async function loadContent(file: SystemLogFile, nextPage = false) {
  contentLoading.value = true;
  try {
    const page = nextPage && logContent.value ? logContent.value.page + 1 : 1;
    const result = await admin.getSystemLogContentApi(file.filename, {
      page,
      page_size: LOG_PAGE_SIZE,
      reverse: true,
    });

    logContent.value =
      nextPage && logContent.value
        ? {
            ...result,
            lines: [...logContent.value.lines, ...result.lines],
          }
        : result;

    if (autoScroll.value && !nextPage) {
      nextTick(() => {
        scrollReaderToTop();
      });
    }
  } catch {
    if (!nextPage) {
      logContent.value = null;
    }
  } finally {
    contentLoading.value = false;
  }
}

function onCategorySelect(code: string) {
  if (code === activeCategory.value) {
    void loadFiles();
    return;
  }
  activeCategory.value = code;
}

function onSelectFile(file: SystemLogFile) {
  selectedFile.value = file;
  void loadContent(file);
}

function onLoadMore() {
  if (selectedFile.value && logContent.value?.hasMore) {
    void loadContent(selectedFile.value, true);
  }
}

async function onDownload(file: SystemLogFile) {
  downloadingFile.value = file.filename;
  try {
    await admin.downloadSystemLogFileApi(file.filename);
    message.success($t('admin.system.systemLog.messages.downloadSuccess'));
  } catch {
    message.error($t('admin.system.systemLog.messages.downloadFail'));
  } finally {
    downloadingFile.value = null;
  }
}

async function onDelete(file: SystemLogFile) {
  try {
    await admin.deleteSystemLogFileApi(file.filename);
    message.success($t('admin.system.systemLog.messages.deleteSuccess'));
    await Promise.all([loadStats(), loadFiles()]);
  } catch {}
}

async function onCopyAll() {
  if (!logContent.value) return;
  const success = await copyToClipboard(logContent.value.lines.join('\n'));
  if (success) {
    message.success($t('admin.system.systemLog.messages.copyAllSuccess'));
  } else {
    message.error($t('admin.system.systemLog.messages.copyManual'));
  }
}

async function onCopyLine(line: string) {
  const success = await copyToClipboard(line);
  if (success) {
    message.success($t('admin.system.systemLog.messages.copySuccess'));
  } else {
    message.error($t('admin.system.systemLog.messages.copyFail'));
  }
}

async function onRefresh() {
  const previousCategory = activeCategory.value;
  await Promise.all([loadStats(), loadCategories()]);

  if (activeCategory.value && activeCategory.value === previousCategory) {
    await loadFiles();
  }
}

async function onRefreshCurrent() {
  if (selectedFile.value) {
    await loadContent(selectedFile.value);
    return;
  }
  await onRefresh();
}

watch(activeCategory, (value, oldValue) => {
  if (value && value !== oldValue) {
    void loadFiles();
  }
});

onMounted(() => {
  void onRefresh();
});

usePageAIAnchor({
  pageKey: 'admin.system.system-logs',
  resource: '/admin/system-logs',
});

usePageAIOperations({
  pageKey: 'admin.system.system-logs',
  operationStrategy: 'append',
  operations: [
    createRefreshPageOperation({
      action: onRefresh,
      description: 'Reload system log stats, categories and files',
    }),
    createKeywordSearchPageOperation({
      label: $t('shared.pageOperation.searchByKeyword'),
      description: 'Search within current log content',
      setKeyword: (keyword) => {
        contentSearchQuery.value = keyword;
      },
    }),
  ],
});
</script>

<template>
  <Page auto-content-height content-class="flex min-h-0 flex-col gap-4 !p-4">
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
              {{ $t('admin.system.systemLog.title') }}
            </h1>
            <span class="hidden text-xs text-muted-foreground xl:inline">
              {{ $t('admin.system.systemLog.pageDesc') }}
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
                v-for="metric in toolbarMetrics"
                :key="metric.key"
                class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
              >
                <span class="mr-1 font-semibold text-foreground">
                  {{ metric.value }}
                </span>
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
              {{ $t('admin.system.systemLog.refresh') }}
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
              {{ $t('admin.system.systemLog.download') }}
            </button>
            <button
              type="button"
              :class="getPillButtonClass()"
              :disabled="!logContent"
              @click="void onCopyAll()"
            >
              <IconifyIcon icon="lucide:copy" class="size-4" />
              {{ $t('admin.system.systemLog.copyAll') }}
            </button>
          </div>
        </div>
      </div>
    </section>

    <section
      class="rounded-[20px] border border-border/70 bg-card px-3 py-3 shadow-sm"
    >
      <div
        class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
      >
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-foreground">
            {{ $t('admin.system.systemLog.categories') }}
          </span>
          <span class="text-xs text-muted-foreground">
            {{ categories.length }}
          </span>
        </div>

        <div
          v-if="loading && categories.length === 0"
          class="grid w-full gap-2 sm:grid-cols-2 xl:max-w-[720px] xl:grid-cols-4"
        >
          <div
            v-for="item in 4"
            :key="item"
            class="rounded-xl border border-border/60 bg-background/80 px-3 py-2"
          >
            <Skeleton active :paragraph="{ rows: 1 }" :title="false" />
          </div>
        </div>

        <div
          v-else
          class="flex gap-2 overflow-x-auto pb-1 xl:flex-wrap xl:justify-end xl:overflow-visible xl:pb-0"
        >
          <button
            v-for="category in categories"
            :key="category.code"
            type="button"
            class="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border px-3 text-left text-sm transition-all"
            :class="
              category.code === activeCategory
                ? `${getCategoryVisual(category.code).activeCard} shadow-sm`
                : 'border-border/60 bg-background/80 hover:border-primary/20 hover:bg-accent/40'
            "
            @click="onCategorySelect(category.code)"
          >
            <span
              class="flex size-7 items-center justify-center rounded-lg"
              :class="getCategoryVisual(category.code).iconWrap"
            >
              <IconifyIcon
                :icon="getCategoryVisual(category.code).icon"
                class="size-3.5"
              />
            </span>
            <span class="font-medium text-foreground">{{ category.name }}</span>
            <span class="text-xs text-muted-foreground">
              {{ category.fileCount }}
            </span>
          </button>
        </div>
      </div>
    </section>

    <section
      class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[280px_minmax(0,1fr)]"
    >
      <aside
        class="flex min-h-[320px] min-w-0 flex-col overflow-hidden rounded-[20px] border border-border/70 bg-card shadow-sm"
      >
        <div class="border-b border-border/60 px-4 py-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-foreground">
                {{ $t('admin.system.systemLog.files') }}
              </div>
              <p class="mt-1 line-clamp-1 text-xs text-muted-foreground">
                {{
                  activeCategoryMeta?.description ||
                  $t('admin.system.systemLog.filesDesc')
                }}
              </p>
            </div>
            <span class="shrink-0 text-xs text-muted-foreground">
              {{ filteredFiles.length }} / {{ files.length }}
            </span>
          </div>

          <div class="mt-3">
            <Input
              v-model:value="fileSearchQuery"
              :placeholder="$t('admin.system.systemLog.searchFiles')"
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
        </div>

        <div class="min-h-0 flex-1 overflow-auto p-2">
          <div v-if="filesLoading" class="space-y-2">
            <div
              v-for="item in 5"
              :key="item"
              class="rounded-xl border border-border/60 bg-background/80 p-3"
            >
              <Skeleton active :paragraph="{ rows: 1 }" :title="false" />
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
                      <Tooltip :title="$t('admin.system.systemLog.download')">
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
                          $t('admin.system.systemLog.messages.deleteConfirm', {
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
                    <span>{{
                      formatDate(file.modifiedAt, 'MM-DD HH:mm')
                    }}</span>
                    <span
                      v-if="file.isCurrent"
                      class="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-200"
                    >
                      {{ $t('admin.system.systemLog.running') }}
                    </span>
                    <span
                      v-if="selectedFile?.filename === file.filename"
                      class="rounded-full bg-primary/10 px-1.5 py-0.5 text-primary"
                    >
                      {{ $t('admin.system.systemLog.current') }}
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
                  ? $t('admin.system.systemLog.emptySearch')
                  : $t('admin.system.systemLog.noFiles')
              "
            />
          </div>
        </div>
      </aside>

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
                      $t('admin.system.systemLog.noSelectedFile')
                    }}
                  </h2>
                </Tooltip>
                <Tag
                  v-if="selectedFile?.isCurrent"
                  color="success"
                  class="!mr-0 rounded-full"
                >
                  {{ $t('admin.system.systemLog.running') }}
                </Tag>
              </div>

              <div class="mt-2 flex flex-wrap gap-2">
                <span
                  v-for="chip in readerMetaChips"
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
                  :placeholder="$t('admin.system.systemLog.searchContent')"
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
                  {{ $t('admin.system.systemLog.refresh') }}
                </button>
                <button
                  type="button"
                  :class="getPillButtonClass(autoScroll)"
                  @click="autoScroll = !autoScroll"
                >
                  <IconifyIcon icon="lucide:arrow-up-to-line" class="size-4" />
                  {{ $t('admin.system.systemLog.autoScroll') }}
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
                      ? $t('admin.system.systemLog.lightTheme')
                      : $t('admin.system.systemLog.darkTheme')
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
              ref="logContainerRef"
              class="scrollbar-thin relative h-full overflow-auto"
            >
              <Spin :spinning="contentLoading" wrapper-class-name="h-full">
                <template v-if="logContent && selectedFile">
                  <div
                    class="min-w-[680px] p-3 font-mono text-xs leading-6 sm:p-4"
                  >
                    <div
                      v-for="(line, index) in renderedLines"
                      :key="`${selectedFile.filename}-${index}`"
                      class="group relative grid grid-cols-[52px_minmax(0,1fr)] gap-3 rounded-lg border border-transparent px-2 py-1 transition-all"
                      :class="[
                        lineHoverClass,
                        line.isMatch ? lineMatchClass : '',
                      ]"
                    >
                      <div
                        class="select-none pt-0.5 text-right text-[11px]"
                        :class="
                          isDarkTheme ? 'text-slate-500' : 'text-slate-400'
                        "
                      >
                        {{ getLineNumber(index) }}
                      </div>

                      <div class="relative min-w-0">
                        <template v-if="line.timestamp">
                          <div class="flex min-w-0 items-start gap-2.5">
                            <span
                              class="shrink-0 pt-0.5 text-[11px]"
                              :class="
                                isDarkTheme
                                  ? 'text-slate-500'
                                  : 'text-slate-400'
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
                        <Tooltip :title="$t('admin.system.systemLog.copyLine')">
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
                        {{ $t('admin.system.systemLog.loadMore') }}
                      </Button>
                      <span
                        v-else
                        class="text-xs"
                        :class="
                          isDarkTheme ? 'text-slate-500' : 'text-slate-400'
                        "
                      >
                        --- {{ $t('admin.system.systemLog.endOfLog') }} ---
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
                    {{ $t('admin.system.systemLog.noSelectedFile') }}
                  </h3>
                  <p class="mt-1 max-w-md text-sm text-muted-foreground">
                    {{ $t('admin.system.systemLog.selectFileTip') }}
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
                {{ $t('admin.system.systemLog.lines') }}:
                {{ displayedLineCount }}
              </span>
              <span>
                {{ $t('admin.system.systemLog.totalLines') }}:
                {{ logContent?.totalLines ?? 0 }}
              </span>
              <span v-if="contentSearchQuery.trim()">
                {{ $t('admin.system.systemLog.matches') }}:
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
                {{ $t('admin.system.systemLog.backToTop') }}
              </button>
            </div>
          </div>
        </div>
      </section>
    </section>
  </Page>
</template>

<style scoped>
.scrollbar-thin::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}

.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgb(148 163 184 / 30%);
  border-radius: 9999px;
}

.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: rgb(148 163 184 / 55%);
}
</style>
