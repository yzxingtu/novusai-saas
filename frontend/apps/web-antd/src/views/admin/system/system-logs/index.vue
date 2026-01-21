<script lang="ts" setup>
/**
 * 系统日志管理页面
 * Vben Admin 风格深度定制
 */
import type { adminApi } from '#/api';

import { computed, nextTick, onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Input,
  message,
  Popconfirm,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { adminApi as admin } from '#/api';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

type SystemLogCategory = adminApi.SystemLogCategory;
type SystemLogFile = adminApi.SystemLogFile;
type SystemLogContent = adminApi.SystemLogContent;
type SystemLogStats = adminApi.SystemLogStats;

// 状态
const loading = ref(false);
const statsLoading = ref(false);
const contentLoading = ref(false);
const stats = ref<SystemLogStats | null>(null);
const categories = ref<SystemLogCategory[]>([]);
const files = ref<SystemLogFile[]>([]);
const activeCategory = ref<string>('');
const selectedFile = ref<SystemLogFile | null>(null);
const logContent = ref<SystemLogContent | null>(null);

// 视图控制
const logSearchQuery = ref('');
const autoScroll = ref(false);
const isDarkTheme = ref(true); // 默认深色模式
const logContainerRef = ref<HTMLDivElement | null>(null);

// 计算高亮的日志行
const highlightLines = computed(() => {
  if (!logContent.value) return [];
  const query = logSearchQuery.value.toLowerCase();
  
  return logContent.value.lines.map(line => {
    const parsed = parseLogLine(line);
    const isMatch = query && line.toLowerCase().includes(query);
    return {
      ...parsed,
      originalLine: line,
      isMatch,
    };
  });
});

/**
 * 复制文本到剪贴板
 */
async function copyToClipboard(text: string) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    } 
    // Fallback for non-secure contexts (e.g. HTTP dev)
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      textArea.remove();
      return true;
    } catch {
      textArea.remove();
      return false;
    }
  } catch {
    return false;
  }
}

/**
 * 加载统计信息
 */
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

/**
 * 加载分类列表
 */
async function loadCategories() {
  loading.value = true;
  try {
    categories.value = await admin.getSystemLogCategoriesApi();
    if (categories.value.length > 0 && !activeCategory.value) {
      activeCategory.value = categories.value[0]!.code;
    }
  } catch {
    categories.value = [];
  } finally {
    loading.value = false;
  }
}

/**
 * 加载文件列表
 */
async function loadFiles() {
  if (!activeCategory.value) return;

  loading.value = true;
  try {
    files.value = await admin.getSystemLogFilesApi({
      category: activeCategory.value,
    });
    // 自动选中第一个
    if (files.value.length > 0) {
      const firstFile = files.value[0]!;
      selectedFile.value = firstFile;
      await loadContent(firstFile);
    } else {
      selectedFile.value = null;
      logContent.value = null;
    }
  } catch {
    files.value = [];
    selectedFile.value = null;
    logContent.value = null;
  } finally {
    loading.value = false;
  }
}

/**
 * 加载日志内容
 */
async function loadContent(file: SystemLogFile, nextPage = false) {
  contentLoading.value = true;
  try {
    const page = nextPage && logContent.value ? logContent.value.page + 1 : 1;
    const result = await admin.getSystemLogContentApi(file.filename, {
      page,
      page_size: 100,
      reverse: true, // 最新在前
    });
    if (nextPage && logContent.value) {
      logContent.value = {
        ...result,
        lines: [...logContent.value.lines, ...result.lines],
      };
    } else {
      logContent.value = result;
    }
    
    // 自动滚动 (仅当 autoScroll 开启且非追加模式，或追加模式下确实需要滚动时)
    if (autoScroll.value && logContainerRef.value && !nextPage) {
      nextTick(() => {
        logContainerRef.value?.scrollTo({ top: 0, behavior: 'smooth' });
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

function onSelectFile(file: SystemLogFile) {
  selectedFile.value = file;
  loadContent(file);
}

function onLoadMore() {
  if (selectedFile.value && logContent.value?.hasMore) {
    loadContent(selectedFile.value, true);
  }
}

function onDownload(file: SystemLogFile) {
  const url = admin.getSystemLogDownloadUrl(file.filename);
  window.open(url, '_blank');
}

async function onDelete(file: SystemLogFile) {
  try {
    await admin.deleteSystemLogFileApi(file.filename);
    message.success($t('admin.system.systemLog.messages.deleteSuccess'));
    await loadFiles();
    await loadStats();
    if (selectedFile.value?.filename === file.filename) {
      selectedFile.value = null;
      logContent.value = null;
    }
  } catch {}
}

/**
 * 复制全部日志
 */
async function onCopyAll() {
  if (!logContent.value) return;
  const success = await copyToClipboard(logContent.value.lines.join('\n'));
  if (success) {
    message.success($t('admin.system.systemLog.messages.copyAllSuccess'));
  } else {
    message.error($t('admin.system.systemLog.messages.copyManual'));
  }
}

/**
 * 复制单行日志
 */
async function onCopyLine(line: string) {
  const success = await copyToClipboard(line);
  if (success) {
    message.success($t('admin.system.systemLog.messages.copySuccess'));
  } else {
    message.error($t('admin.system.systemLog.messages.copyFail'));
  }
}

async function onRefresh() {
  await Promise.all([loadStats(), loadCategories()]);
  if (activeCategory.value) {
    await loadFiles();
  }
}

function parseLogLine(line: string): { timestamp: string; level: string; content: string; isStackTrace: boolean } {
  // 宽松匹配，适配更多格式
  const match = line.match(/^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\|\s*([A-Z]+)\s*\|\s*(.*)$/i);
  if (match) {
    return {
      timestamp: match[1] || '',
      level: match[2]?.toUpperCase() || '',
      content: match[3] || '',
      isStackTrace: false,
    };
  }
  return {
    timestamp: '',
    level: '',
    content: line,
    isStackTrace: line.startsWith('  ') || line.startsWith('\t') || line.includes('File "') || line.includes('Traceback'),
  };
}

/**
 * 日志级别样式 (根据深色/浅色模式动态调整)
 */
function getLevelBadgeClass(level: string): string {
  switch (level) {
    case 'ERROR':
    case 'FATAL':
    case 'CRITICAL':
      return isDarkTheme.value 
        ? 'bg-red-500/20 text-red-400 border border-red-500/30' 
        : 'bg-red-50 text-red-600 border border-red-200';
    case 'WARN':
    case 'WARNING':
      return isDarkTheme.value 
        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' 
        : 'bg-amber-50 text-amber-600 border border-amber-200';
    case 'INFO':
      return isDarkTheme.value 
        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' 
        : 'bg-blue-50 text-blue-600 border border-blue-200';
    case 'DEBUG':
      // 紫色/靛青色，不再是灰色
      return isDarkTheme.value 
        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' 
        : 'bg-purple-50 text-purple-600 border border-purple-200';
    case 'SUCCESS':
      return isDarkTheme.value 
        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
        : 'bg-emerald-50 text-emerald-600 border border-emerald-200';
    default:
      return isDarkTheme.value 
        ? 'bg-gray-500/20 text-gray-400 border border-gray-500/30' 
        : 'bg-gray-100 text-gray-500 border border-gray-200';
  }
}

function getContentClass(parsed: ReturnType<typeof parseLogLine>): string {
  if (parsed.isStackTrace) {
    return 'text-red-400/80 italic font-mono';
  }
  if (!isDarkTheme.value) {
    // 浅色模式下的文字颜色
    return 'text-gray-700'; 
  }
  // 深色模式下的文字颜色
  switch (parsed.level) {
    case 'ERROR': return 'text-red-300';
    case 'WARN': return 'text-amber-200';
    case 'INFO': return 'text-blue-200';
    case 'DEBUG': return 'text-purple-300'; // 紫色高亮
    case 'SUCCESS': return 'text-emerald-300';
    default: return 'text-gray-300';
  }
}

watch(activeCategory, () => {
  loadFiles();
});

onMounted(() => {
  onRefresh();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <!-- 1. 顶部统计卡片 (重写) -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <!-- 文件总数 -->
      <div class="bg-card relative overflow-hidden rounded-xl border p-4 shadow-sm transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-muted-foreground text-sm font-medium">{{ $t('admin.system.systemLog.totalFiles') }}</p>
            <h3 class="text-foreground mt-2 text-2xl font-bold">
              <Spin v-if="statsLoading" size="small" />
              <span v-else>{{ stats?.totalFiles ?? 0 }}</span>
            </h3>
          </div>
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30">
            <IconifyIcon icon="lucide:files" class="text-2xl" />
          </div>
        </div>
      </div>

      <!-- 总大小 -->
      <div class="bg-card relative overflow-hidden rounded-xl border p-4 shadow-sm transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-muted-foreground text-sm font-medium">{{ $t('admin.system.systemLog.totalSize') }}</p>
            <h3 class="text-foreground mt-2 text-2xl font-bold">
              <Spin v-if="statsLoading" size="small" />
              <span v-else>{{ stats?.totalSizeFormatted ?? '-' }}</span>
            </h3>
          </div>
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-emerald-600 text-white shadow-lg shadow-emerald-500/30">
            <IconifyIcon icon="lucide:hard-drive" class="text-2xl" />
          </div>
        </div>
      </div>

      <!-- 日志分类 -->
      <div class="bg-card relative overflow-hidden rounded-xl border p-4 shadow-sm transition-all hover:shadow-md">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-muted-foreground text-sm font-medium">{{ $t('admin.system.systemLog.categories') }}</p>
            <h3 class="text-foreground mt-2 text-2xl font-bold">
              <Spin v-if="loading" size="small" />
              <span v-else>{{ categories.length }}</span>
            </h3>
          </div>
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-purple-500 to-purple-600 text-white shadow-lg shadow-purple-500/30">
            <IconifyIcon icon="lucide:folder-tree" class="text-2xl" />
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 主内容区域 -->
    <div class="bg-card flex flex-1 gap-4 overflow-hidden rounded-xl p-1 shadow-sm">
      
      <!-- 左侧：文件列表 (折叠面板风格) -->
      <div class="flex w-[320px] flex-shrink-0 flex-col border-r">
        <!-- 头部 -->
        <div class="flex items-center justify-between border-b p-3">
          <span class="text-foreground font-semibold">{{ $t('admin.system.systemLog.files') }}</span>
          <Button type="text" size="small" :loading="loading" @click="onRefresh">
            <template #icon><IconifyIcon icon="lucide:refresh-cw" /></template>
          </Button>
        </div>

        <!-- 分类与文件列表 -->
        <div class="flex-1 overflow-y-auto p-2">
          <Spin :spinning="loading && categories.length === 0">
            <div class="flex flex-col gap-1">
              <template v-for="cat in categories" :key="cat.code">
                <!-- 分类标题 -->
                <div 
                  class="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors hover:bg-accent"
                  :class="activeCategory === cat.code ? 'bg-accent text-foreground font-medium' : 'text-muted-foreground'"
                  @click="activeCategory = cat.code"
                >
                  <div class="flex items-center gap-2">
                    <IconifyIcon 
                      :icon="activeCategory === cat.code ? 'lucide:folder-open' : 'lucide:folder'" 
                      class="text-base"
                      :class="activeCategory === cat.code ? 'text-primary' : 'text-muted-foreground'"
                    />
                    <span>{{ cat.name }}</span>
                  </div>
                  <Tag :bordered="false" class="bg-accent text-muted-foreground !mr-0 shadow-sm">
                    {{ cat.fileCount }}
                  </Tag>
                </div>

                <!-- 该分类下的文件列表 (仅当分类选中时显示) -->
                <div v-show="activeCategory === cat.code" class="pl-4">
                  <!-- 文件加载中 -->
                  <div v-if="loading && files.length === 0" class="text-muted-foreground py-2 text-center text-xs">
                    <Spin size="small" />
                  </div>
                  
                  <!-- 文件列表 -->
                  <div v-else-if="files.length > 0" class="flex flex-col gap-1 border-l py-1 pl-2">
                    <div 
                      v-for="file in files" 
                      :key="file.filename"
                      class="group relative cursor-pointer rounded-md px-3 py-2 transition-all hover:bg-primary/10"
                      :class="selectedFile?.filename === file.filename 
                        ? 'bg-primary/10 text-primary' 
                        : 'text-muted-foreground'"
                      @click="onSelectFile(file)"
                    >
                      <div class="flex items-center justify-between">
                        <span class="truncate text-xs font-medium">{{ file.filename }}</span>
                        <div class="flex items-center gap-1">
                          <Tag v-if="file.isCurrent" color="processing" class="!mr-0 !h-4 !px-1 !text-[10px] !leading-4">
                            {{ $t('admin.system.systemLog.running') }}
                          </Tag>
                          <Tag v-if="selectedFile?.filename === file.filename" color="green" class="!mr-0 !h-4 !px-1 !text-[10px] !leading-4">
                            {{ $t('admin.system.systemLog.current') }}
                          </Tag>
                        </div>
                      </div>
                      
                      <div class="mt-1 flex items-center justify-between text-[10px] opacity-70">
                        <span>{{ file.sizeFormatted }}</span>
                        <span>{{ formatDate(file.modifiedAt, 'MM-DD') }}</span>
                      </div>

                      <!-- 悬停操作 -->
                      <div class="bg-card absolute right-1 top-1.5 hidden gap-1 rounded p-0.5 shadow-sm group-hover:flex">
                        <Tooltip :title="$t('admin.system.systemLog.download')">
                          <IconifyIcon 
                            icon="lucide:download" 
                            class="hover:bg-accent cursor-pointer rounded p-1 hover:text-primary" 
                            @click.stop="onDownload(file)"
                          />
                        </Tooltip>
                        <Popconfirm :title="$t('admin.system.systemLog.messages.deleteConfirm', { name: file.filename })" @confirm="onDelete(file)">
                          <Tooltip :title="$t('admin.system.systemLog.delete')">
                            <IconifyIcon 
                              icon="lucide:trash-2" 
                              class="hover:bg-accent cursor-pointer rounded p-1 hover:text-red-500" 
                              @click.stop
                            />
                          </Tooltip>
                        </Popconfirm>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 无文件 -->
                  <div v-else class="text-muted-foreground py-2 text-center text-xs">
                    {{ $t('admin.system.systemLog.noFiles') }}
                  </div>
                </div>
              </template>
            </div>
          </Spin>
        </div>
      </div>

      <!-- 右侧：日志详情 (重写) -->
      <div class="bg-card flex flex-1 flex-col overflow-hidden">
        <!-- 头部工具栏 -->
        <div class="flex h-14 items-center justify-between border-b px-4">
          <div class="flex items-center gap-3">
             <div class="text-foreground flex items-center gap-2 text-sm font-medium">
               <IconifyIcon icon="lucide:terminal-square" class="text-primary" />
               {{ selectedFile?.filename || $t('admin.system.systemLog.noSelectedFile') }}
             </div>
             <Tag v-if="selectedFile?.isCurrent" color="success" class="!m-0">{{ $t('admin.system.systemLog.running') }}</Tag>
          </div>
          
          <div class="flex items-center gap-3">
             <!-- 搜索 -->
             <Input
               v-model:value="logSearchQuery"
               :placeholder="$t('admin.system.systemLog.searchContent')"
               size="small"
               class="w-48"
               allow-clear
             >
               <template #prefix><IconifyIcon icon="lucide:search" class="text-gray-400" /></template>
             </Input>
             
             <div class="bg-border h-4 w-px"></div>

             <!-- 操作按钮组 -->
             <Tooltip :title="$t('admin.system.systemLog.toggleTheme')">
               <Button type="text" size="small" @click="isDarkTheme = !isDarkTheme">
                 <template #icon>
                   <IconifyIcon :icon="isDarkTheme ? 'lucide:sun' : 'lucide:moon'" />
                 </template>
               </Button>
             </Tooltip>

             <Tooltip :title="$t('admin.system.systemLog.copyAll')">
               <Button type="text" size="small" @click="onCopyAll" class="flex items-center gap-1">
                 <template #icon><IconifyIcon icon="lucide:copy" /></template>
                 <span class="hidden sm:inline">{{ $t('admin.system.systemLog.copyAll') }}</span>
               </Button>
             </Tooltip>

             <Tooltip :title="$t('admin.system.systemLog.backToTop')">
               <Button type="text" size="small" @click="logContainerRef?.scrollTo({ top: 0, behavior: 'smooth' })">
                 <template #icon><IconifyIcon icon="lucide:arrow-up-to-line" /></template>
               </Button>
             </Tooltip>
          </div>
        </div>

        <!-- 日志内容容器 -->
        <div 
          ref="logContainerRef"
          class="flex-1 overflow-auto scrollbar-thin relative"
          :class="isDarkTheme ? 'bg-[#1e1e1e] text-gray-300' : 'bg-white text-gray-800'"
        >
          <Spin :spinning="contentLoading" wrapperClassName="h-full">
            <template v-if="logContent && selectedFile">
              <div class="min-w-fit p-4 font-mono text-xs leading-6">
                <div 
                  v-for="(item, index) in highlightLines" 
                  :key="index"
                  class="group flex border-l-2 border-transparent pl-2 hover:bg-black/5 dark:hover:bg-white/5 relative"
                  :class="{'bg-yellow-100/50 dark:bg-yellow-500/20': item.isMatch}"
                >
                  <!-- 行号 -->
                  <div class="w-10 flex-shrink-0 select-none text-right opacity-30">{{ index + logContent.page * 100 - 99 }}</div>
                  
                  <!-- 日志本体 -->
                  <div class="relative ml-4 flex min-w-0 flex-1 gap-3">
                    <template v-if="item.timestamp">
                      <span class="flex-shrink-0 opacity-50">{{ item.timestamp }}</span>
                      <span 
                        class="flex w-16 flex-shrink-0 items-center justify-center rounded px-1 text-[10px] font-bold"
                        :class="getLevelBadgeClass(item.level)"
                      >
                        {{ item.level }}
                      </span>
                      <span class="whitespace-pre-wrap break-all transition-colors" :class="getContentClass(item)">
                        {{ item.content }}
                      </span>
                    </template>
                    <template v-else>
                      <span class="whitespace-pre-wrap break-all" :class="getContentClass(item)">
                        {{ item.content }}
                      </span>
                    </template>
                  </div>

                  <!-- 单行复制按钮 (悬停显示) - 绝对定位到行末尾 -->
                  <div class="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover:flex z-10">
                    <Tooltip :title="$t('admin.system.systemLog.copyLine')">
                       <button 
                         class="flex h-6 w-6 items-center justify-center rounded bg-primary/10 text-primary shadow-sm hover:bg-primary hover:text-white transition-colors"
                         @click.stop="onCopyLine(item.originalLine)"
                       >
                         <IconifyIcon icon="lucide:copy" class="text-xs" />
                       </button>
                    </Tooltip>
                  </div>
                </div>

                <!-- 加载更多 -->
                <div class="mt-8 flex justify-center pb-8">
                  <Button 
                    v-if="logContent.hasMore" 
                    type="dashed" 
                    :loading="contentLoading"
                    @click="onLoadMore"
                  >
                    {{ $t('admin.system.systemLog.loadMore') }}
                  </Button>
                  <span v-else class="text-xs opacity-40">--- {{ $t('admin.system.systemLog.endOfLog') }} ---</span>
                </div>
              </div>
            </template>
            
            <div v-else class="flex h-full flex-col items-center justify-center opacity-30">
              <IconifyIcon icon="lucide:file-code" class="text-6xl" />
              <span class="mt-4 text-sm">{{ $t('admin.system.systemLog.selectFileTip') }}</span>
            </div>
          </Spin>
        </div>

        <!-- 底部状态栏 -->
        <div class="flex h-8 items-center justify-between border-t border-gray-100 bg-gray-50 px-4 text-xs text-gray-500 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400">
           <div class="flex gap-4">
             <span>{{ $t('admin.system.systemLog.lines') }}: {{ logContent?.lines?.length || 0 }}</span>
             <span>{{ $t('admin.system.systemLog.totalLines') }}: {{ logContent?.totalLines || 0 }}</span>
           </div>
           <div class="flex gap-4">
             <span>{{ selectedFile?.sizeFormatted }}</span>
             <span>UTF-8</span>
           </div>
        </div>
      </div>
    </div>
  </Page>
</template>

<style scoped>
/* 滚动条样式优化 */
.scrollbar-thin::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: rgba(156, 163, 175, 0.3);
  border-radius: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: rgba(156, 163, 175, 0.5);
}
</style>
