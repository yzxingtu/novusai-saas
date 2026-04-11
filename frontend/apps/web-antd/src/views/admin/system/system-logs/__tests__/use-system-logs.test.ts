// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils';
import { defineComponent, nextTick } from 'vue';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  SystemLogCategory,
  SystemLogContent,
  SystemLogFile,
  SystemLogStats,
} from '#/api';

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

const DEFAULT_STATS: SystemLogStats = {
  totalFiles: 0,
  totalSize: 0,
  totalSizeFormatted: '0 B',
};

function mountHarness(): SystemLogsVm {
  const wrapper = mount(
    defineComponent({
      name: 'SystemLogsHarness',
      setup() {
        return provideSystemLogsContext();
      },
      render: () => null,
    }),
  );

  return wrapper.vm as unknown as SystemLogsVm;
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
): SystemLogContent {
  return {
    filename,
    hasMore,
    lines,
    page,
    pageSize: 120,
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

    vm.logContent = createContent('app.log', [
      '2026-04-12 12:34:56 | INFO | Hello world',
      '  File "app.py", line 1, in <module>',
      'Traceback (most recent call last):',
      'plain line without timestamp',
    ]);

    await nextTick();

    const [first, second, third, fourth] = vm.renderedLines;

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

    expect(vm.activeCategory).toBe('app');
    expect(vm.selectedFile?.filename).toBe('app.log');

    vm.onCategorySelect('app');
    await flushPromises();

    expect(mockAdminApi.getSystemLogFilesApi).toHaveBeenCalledTimes(2);
    expect(vm.activeCategory).toBe('app');
    expect(vm.selectedFile?.filename).toBe('app.log');
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

    expect(vm.activeCategory).toBe('app');
    expect(vm.files).toEqual([appFile]);
    expect(vm.selectedFile?.filename).toBe('app.log');

    vm.onCategorySelect('error');
    await flushPromises();

    expect(mockAdminApi.getSystemLogFilesApi).toHaveBeenCalledTimes(2);
    expect(mockAdminApi.getSystemLogFilesApi).toHaveBeenLastCalledWith({
      category: 'error',
    });
    expect(vm.activeCategory).toBe('error');
    expect(vm.files).toEqual([errorFile]);
    expect(vm.selectedFile?.filename).toBe('error.log');
  });

  it('appends content when loading the next page', async () => {
    const vm = mountHarness();
    await flushPromises();

    const file = createFile('app.log', 'app');
    vm.logContent = createContent('app.log', ['first'], 1, true);
    await nextTick();

    mockAdminApi.getSystemLogContentApi.mockResolvedValueOnce(
      createContent('app.log', ['second'], 2, false),
    );

    await vm.loadContent(file, true);
    await flushPromises();

    const [filename, params] =
      mockAdminApi.getSystemLogContentApi.mock.calls.at(-1) ?? [];

    expect(filename).toBe('app.log');
    expect(params).toEqual({ page: 2, page_size: 120, reverse: true });
    expect(vm.logContent?.lines).toEqual(['first', 'second']);
    expect(vm.logContent?.page).toBe(2);
  });

  it('counts matched lines against the search query', async () => {
    const vm = mountHarness();
    await flushPromises();

    vm.logContent = createContent('app.log', [
      '2026-04-12 12:34:56 | INFO | Hello',
      '2026-04-12 12:34:57 | ERROR | Something failed',
      'plain error line',
    ]);

    await nextTick();
    vm.contentSearchQuery = 'error';
    await nextTick();

    expect(vm.matchedLineCount).toBe(2);
  });
});
