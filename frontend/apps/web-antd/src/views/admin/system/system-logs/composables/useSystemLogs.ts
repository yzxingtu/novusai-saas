import type { adminApi } from '#/api';

import {
  computed,
  inject,
  nextTick,
  onMounted,
  provide,
  ref,
  watch,
} from 'vue';

import { message } from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t as t } from '#/locales';
import { copyToClipboard } from '#/utils/common';

const LOG_PAGE_SIZE = 120;

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

const systemLogsSymbol = Symbol('system-logs-context');

export type SystemLogsContext = ReturnType<typeof createSystemLogsContext>;

export function provideSystemLogsContext() {
  const context = createSystemLogsContext();
  provide(systemLogsSymbol, context);
  return context;
}

export function useSystemLogsContext() {
  const context = inject<SystemLogsContext>(systemLogsSymbol);
  if (!context) {
    throw new Error('System logs context is not provided');
  }
  return context;
}

function createSystemLogsContext() {
  const loading = ref(false);
  const filesLoading = ref(false);
  const statsLoading = ref(false);
  const contentLoading = ref(false);
  const downloadingFile = ref<null | string>(null);

  const stats = ref<adminApi.SystemLogStats | null>(null);
  const categories = ref<adminApi.SystemLogCategory[]>([]);
  const files = ref<adminApi.SystemLogFile[]>([]);
  const activeCategory = ref('');
  const selectedFile = ref<adminApi.SystemLogFile | null>(null);
  const logContent = ref<adminApi.SystemLogContent | null>(null);

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

  const matchedLineCount = computed(() =>
    renderedLines.value.reduce(
      (total, line) => total + (line.isMatch ? 1 : 0),
      0,
    ),
  );

  const displayedLineCount = computed(
    () => logContent.value?.lines.length ?? 0,
  );

  const toolbarMetrics = computed(() => {
    return [
      {
        key: 'total-files',
        labelKey: 'admin.system.systemLog.totalFiles',
        value: String(stats.value?.totalFiles ?? 0),
      },
      {
        key: 'total-size',
        labelKey: 'admin.system.systemLog.totalSize',
        value: stats.value?.totalSizeFormatted ?? '-',
      },
      {
        key: 'categories',
        labelKey: 'admin.system.systemLog.categories',
        value: String(categories.value.length),
      },
    ];
  });

  const readerShellClass = computed(() =>
    isDarkTheme.value
      ? 'border-slate-900 bg-slate-950 text-slate-100'
      : 'border-stone-200 bg-white text-slate-800',
  );

  const readerStatusBarClass = computed(() =>
    isDarkTheme.value
      ? 'border-slate-800/80 bg-slate-900/70 text-slate-400'
      : 'border-border/60 bg-background/80 text-muted-foreground',
  );

  const lineHoverClass = computed(() =>
    isDarkTheme.value ? 'hover:bg-white/5' : 'hover:bg-primary/5',
  );

  const lineMatchClass = computed(() =>
    isDarkTheme.value
      ? 'border-amber-300/30 bg-amber-400/10'
      : 'border-amber-200 bg-amber-50',
  );

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

  async function loadContent(file: adminApi.SystemLogFile, nextPage = false) {
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

  function onSelectFile(file: adminApi.SystemLogFile) {
    selectedFile.value = file;
    void loadContent(file);
  }

  function onLoadMore() {
    if (selectedFile.value && logContent.value?.hasMore) {
      void loadContent(selectedFile.value, true);
    }
  }

  async function onDownload(file: adminApi.SystemLogFile) {
    downloadingFile.value = file.filename;
    try {
      await admin.downloadSystemLogFileApi(file.filename);
      message.success(t('admin.system.systemLog.messages.downloadSuccess'));
    } catch {
      message.error(t('admin.system.systemLog.messages.downloadFail'));
    } finally {
      downloadingFile.value = null;
    }
  }

  async function onDelete(file: adminApi.SystemLogFile) {
    try {
      await admin.deleteSystemLogFileApi(file.filename);
      message.success(t('admin.system.systemLog.messages.deleteSuccess'));
      await Promise.all([loadStats(), loadFiles()]);
    } catch {}
  }

  async function onCopyAll() {
    if (!logContent.value) return;
    const success = await copyToClipboard(logContent.value.lines.join('\n'));
    if (success) {
      message.success(t('admin.system.systemLog.messages.copyAllSuccess'));
    } else {
      message.error(t('admin.system.systemLog.messages.copyManual'));
    }
  }

  async function onCopyLine(line: string) {
    const success = await copyToClipboard(line);
    if (success) {
      message.success(t('admin.system.systemLog.messages.copySuccess'));
    } else {
      message.error(t('admin.system.systemLog.messages.copyFail'));
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

  return {
    loading,
    filesLoading,
    statsLoading,
    contentLoading,
    downloadingFile,
    stats,
    categories,
    files,
    activeCategory,
    selectedFile,
    logContent,
    fileSearchQuery,
    contentSearchQuery,
    autoScroll,
    isDarkTheme,
    logContainerRef,
    activeCategoryMeta,
    filteredFiles,
    renderedLines,
    matchedLineCount,
    displayedLineCount,
    toolbarMetrics,
    readerShellClass,
    readerStatusBarClass,
    lineHoverClass,
    lineMatchClass,
    getCategoryVisual,
    getPillButtonClass,
    getIconButtonClass,
    getLevelBadgeClass,
    getContentClass,
    getLineNumber,
    scrollReaderToTop,
    loadStats,
    loadCategories,
    loadFiles,
    loadContent,
    onCategorySelect,
    onSelectFile,
    onLoadMore,
    onDownload,
    onDelete,
    onCopyAll,
    onCopyLine,
    onRefresh,
    onRefreshCurrent,
  } as const;
}
