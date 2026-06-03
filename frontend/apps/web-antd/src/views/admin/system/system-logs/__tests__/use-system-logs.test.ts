import type { adminApi } from '#/api';

// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { provideSystemLogsContext } from '../composables/useSystemLogs';

const mockAdminApi = vi.hoisted(() => ({
  deleteSystemLogFileApi: vi.fn(),
  downloadSystemLogFileApi: vi.fn(),
  getSystemLogCategoriesApi: vi.fn(),
  getSystemLogContentApi: vi.fn(),
  getSystemLogFilesApi: vi.fn(),
  getSystemLogStatsApi: vi.fn(),
}));

vi.mock('#/api', () => ({
  adminApi: mockAdminApi,
}));

vi.mock('#/locales', () => ({
  $t: (key: string) => key,
}));

vi.mock('#/utils/common', () => ({
  copyToClipboard: vi.fn().mockResolvedValue(true),
}));

vi.mock('ant-design-vue', () => ({
  message: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

type SystemLogsVm = ReturnType<typeof provideSystemLogsContext>;

type SystemLogCategory = adminApi.SystemLogCategory;
type SystemLogContent = adminApi.SystemLogContent;
type SystemLogFile = adminApi.SystemLogFile;
type SystemLogSearchScope = adminApi.SystemLogSearchScope;
type SystemLogStats = adminApi.SystemLogStats;

const DEFAULT_STATS: SystemLogStats = {
  totalFiles: 0,
  totalSize: 0,
  totalSizeFormatted: '0 B',
};

function mountHarness(): SystemLogsVm {
  let context: null | SystemLogsVm = null;
  mount(
    defineComponent({
      name: 'SystemLogsHarness',
      setup() {
        context = provideSystemLogsContext();
        return () => null;
      },
    }),
  );
  if (!context) {
    throw new Error('System logs context not initialized');
  }

  return context;
}

function createCategory(code: string): SystemLogCategory {
  return {
    code,
    description: '',
    fileCount: 1,
    name: code,
    totalSize: 100,
    totalSizeFormatted: '100 B',
  };
}

function createFile(filename: string, category = 'app'): SystemLogFile {
  return {
    category,
    filename,
    isCurrent: false,
    modifiedAt: '2026-04-12 10:00:00',
    size: 100,
    sizeFormatted: '100 B',
  };
}

function createContent(
  filename: string,
  lines: string[],
  page = 1,
  hasMore = false,
  scope: SystemLogSearchScope = 'current_file',
): SystemLogContent {
  return {
    category: 'app',
    filename,
    hasMore,
    items: lines.map((line, index) => ({
      content: line,
      fileName: filename,
      lineNumber: index + 1,
    })),
    lines,
    page,
    pageSize: 120,
    scope,
    searchedFiles: scope === 'category' ? 2 : 1,
    totalEntries: lines.length,
    totalLines: lines.length,
  };
}

beforeEach(() => {
  mockAdminApi.deleteSystemLogFileApi.mockReset();
  mockAdminApi.downloadSystemLogFileApi.mockReset();
  mockAdminApi.getSystemLogCategoriesApi.mockReset();
  mockAdminApi.getSystemLogContentApi.mockReset();
  mockAdminApi.getSystemLogFilesApi.mockReset();
  mockAdminApi.getSystemLogStatsApi.mockReset();

  mockAdminApi.getSystemLogStatsApi.mockResolvedValue(DEFAULT_STATS);
  mockAdminApi.getSystemLogCategoriesApi.mockResolvedValue([]);
  mockAdminApi.getSystemLogFilesApi.mockResolvedValue([]);
  mockAdminApi.getSystemLogContentApi.mockResolvedValue(
    createContent('empty.log', []),
  );
});

describe('useSystemLogs', () => {
  it('parses timestamp, stack trace, and plain lines from rendered lines', async () => {
    const vm = mountHarness();
    await flushPromises();

    vm.logContent.value = createContent('app.log', [
      '2026-04-12 12:34:56 | INFO | Hello world',
      '  File "app.py", line 1, in <module>',
      'Traceback (most recent call last):',
      'plain line without timestamp',
    ]);

    await nextTick();

    const [first, second, third, fourth] = vm.renderedLines.value;
    if (!first || !second || !third || !fourth) {
      throw new Error('Rendered lines are missing');
    }

    expect(first.timestamp).toBe('2026-04-12 12:34:56');
    expect(first.level).toBe('INFO');
    expect(first.content).toBe('Hello world');
    expect(first.isStackTrace).toBe(false);

    expect(second.isStackTrace).toBe(true);
    expect(second.timestamp).toBe('');
    expect(third.isStackTrace).toBe(true);
    expect(fourth.isStackTrace).toBe(false);
    expect(fourth.timestamp).toBe('');
    expect(fourth.level).toBe('');
    expect(fourth.content).toBe('plain line without timestamp');
  });

  it('keeps the active category and selected file when refreshing files', async () => {
    const firstFile = createFile('app.log', 'app');
    const secondFile = createFile('app-2.log', 'app');

    mockAdminApi.getSystemLogCategoriesApi.mockResolvedValue([
      createCategory('app'),
      createCategory('error'),
    ]);
    mockAdminApi.getSystemLogFilesApi
      .mockResolvedValueOnce([firstFile])
      .mockResolvedValueOnce([firstFile, secondFile]);
    mockAdminApi.getSystemLogContentApi.mockResolvedValue(
      createContent('app.log', ['line']),
    );

    const vm = mountHarness();
    await flushPromises();

    expect(vm.activeCategory.value).toBe('app');
    expect(vm.selectedFile.value?.filename).toBe('app.log');

    vm.onCategorySelect('app');
    await flushPromises();

    expect(mockAdminApi.getSystemLogFilesApi).toHaveBeenCalledTimes(2);
    expect(vm.activeCategory.value).toBe('app');
    expect(vm.selectedFile.value?.filename).toBe('app.log');
  });

  it('updates the file list when switching categories', async () => {
    const appFile = createFile('app.log', 'app');
    const errorFile = createFile('error.log', 'error');

    mockAdminApi.getSystemLogCategoriesApi.mockResolvedValue([
      createCategory('app'),
      createCategory('error'),
    ]);
    mockAdminApi.getSystemLogFilesApi
      .mockResolvedValueOnce([appFile])
      .mockResolvedValueOnce([errorFile]);
    mockAdminApi.getSystemLogContentApi
      .mockResolvedValueOnce(createContent('app.log', ['app line']))
      .mockResolvedValueOnce(createContent('error.log', ['error line']));

    const vm = mountHarness();
    await flushPromises();

    expect(vm.activeCategory.value).toBe('app');
    expect(vm.files.value).toEqual([appFile]);
    expect(vm.selectedFile.value?.filename).toBe('app.log');

    vm.onCategorySelect('error');
    await flushPromises();

    expect(mockAdminApi.getSystemLogFilesApi).toHaveBeenCalledTimes(2);
    expect(mockAdminApi.getSystemLogFilesApi).toHaveBeenLastCalledWith({
      category: 'error',
    });
    expect(vm.activeCategory.value).toBe('error');
    expect(vm.files.value).toEqual([errorFile]);
    expect(vm.selectedFile.value?.filename).toBe('error.log');
  });

  it('appends content when loading the next page', async () => {
    const vm = mountHarness();
    await flushPromises();

    const file = createFile('app.log', 'app');
    vm.logContent.value = createContent('app.log', ['first'], 1, true);
    await nextTick();

    mockAdminApi.getSystemLogContentApi.mockResolvedValueOnce(
      createContent('app.log', ['second'], 2, false),
    );

    await vm.loadContent(file, true);
    await flushPromises();

    const [filename, params] =
      mockAdminApi.getSystemLogContentApi.mock.calls.at(-1) ?? [];

    expect(filename).toBe('app.log');
    expect(params).toEqual({
      page: 2,
      page_size: 120,
      reverse: true,
      scope: 'current_file',
    });
    expect(vm.logContent.value?.lines).toEqual(['first', 'second']);
    expect(vm.logContent.value?.page).toBe(2);
  });

  it('counts matched lines against the search query', async () => {
    const vm = mountHarness();
    await flushPromises();

    vm.logContent.value = createContent('app.log', [
      '2026-04-12 12:34:56 | INFO | Hello',
      '2026-04-12 12:34:57 | ERROR | Something failed',
      'plain error line',
    ]);

    await nextTick();
    vm.searchKeyword.value = 'error';
    await nextTick();

    expect(vm.matchedLineCount.value).toBe(2);
  });

  it('passes keyword, date range, and category scope to the backend search', async () => {
    const appFile = createFile('app.log', 'app');
    mockAdminApi.getSystemLogCategoriesApi.mockResolvedValue([
      createCategory('app'),
    ]);
    mockAdminApi.getSystemLogFilesApi.mockResolvedValue([appFile]);
    mockAdminApi.getSystemLogContentApi.mockResolvedValue(
      createContent(
        'app.log',
        ['2026-04-12 09:00:00 | INFO | trace'],
        1,
        false,
      ),
    );

    const vm = mountHarness();
    await flushPromises();

    vm.searchKeyword.value = 'trace';
    vm.searchScope.value = 'category';
    vm.searchDateRange.value = [
      {
        format: () => '2026-04-10',
      } as never,
      {
        format: () => '2026-04-12',
      } as never,
    ];

    await vm.onApplyFilters();
    await flushPromises();

    const [filename, params] =
      mockAdminApi.getSystemLogContentApi.mock.calls.at(-1) ?? [];

    expect(filename).toBe('app.log');
    expect(params).toEqual({
      end_date: '2026-04-12',
      keyword: 'trace',
      page: 1,
      page_size: 120,
      reverse: true,
      scope: 'category',
      start_date: '2026-04-10',
    });
  });

  it('renders backend line metadata for category-wide results', async () => {
    const vm = mountHarness();
    await flushPromises();

    vm.logContent.value = {
      ...createContent(
        'app.log',
        ['2026-04-12 12:34:56 | INFO | first'],
        1,
        false,
        'category',
      ),
      items: [
        {
          content: '2026-04-12 12:34:56 | INFO | first',
          fileName: 'app.2026-04-12.log',
          lineNumber: 42,
        },
      ],
    };

    await nextTick();

    const firstLine = vm.renderedLines.value[0];
    if (!firstLine) {
      throw new Error('Expected a rendered log line');
    }

    expect(firstLine.fileName).toBe('app.2026-04-12.log');
    expect(firstLine.lineNumber).toBe(42);
    expect(vm.shouldShowFileBadge(firstLine)).toBe(true);
  });
});
