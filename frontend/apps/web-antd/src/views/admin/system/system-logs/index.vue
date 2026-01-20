<script lang="ts" setup>
/**
 * 系统日志管理页面
 * 分类 Tabs + 文件列表 + 内容查看
 */
import type { adminApi } from '#/api';

import { onMounted, ref, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  List,
  ListItem,
  ListItemMeta,
  message,
  Popconfirm,
  Spin,
  Statistic,
  Tabs,
  TabPane,
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
    // 默认选中第一个分类
    if (categories.value.length > 0 && !activeCategory.value) {
      activeCategory.value = categories.value[0]!.name;
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
    // 重置选中的文件
    selectedFile.value = null;
    logContent.value = null;
  } catch {
    files.value = [];
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
      // 追加内容
      logContent.value = {
        ...result,
        lines: [...logContent.value.lines, ...result.lines],
      };
    } else {
      logContent.value = result;
    }
  } catch {
    if (!nextPage) {
      logContent.value = null;
    }
  } finally {
    contentLoading.value = false;
  }
}

/**
 * 选中文件
 */
function onSelectFile(file: SystemLogFile) {
  selectedFile.value = file;
  loadContent(file);
}

/**
 * 加载更多内容
 */
function onLoadMore() {
  if (selectedFile.value && logContent.value?.hasMore) {
    loadContent(selectedFile.value, true);
  }
}

/**
 * 下载文件
 */
function onDownload(file: SystemLogFile) {
  const url = admin.getSystemLogDownloadUrl(file.filename);
  window.open(url, '_blank');
}

/**
 * 删除文件
 */
async function onDelete(file: SystemLogFile) {
  try {
    await admin.deleteSystemLogFileApi(file.filename);
    message.success($t('admin.system.systemLog.messages.deleteSuccess'));
    // 刷新列表
    await loadFiles();
    await loadStats();
    // 如果删除的是当前选中的文件，清空内容
    if (selectedFile.value?.filename === file.filename) {
      selectedFile.value = null;
      logContent.value = null;
    }
  } catch {
    // Error handled by request interceptor
  }
}

/**
 * 刷新数据
 */
async function onRefresh() {
  await Promise.all([loadStats(), loadCategories()]);
  if (activeCategory.value) {
    await loadFiles();
  }
}

// 监听分类切换
watch(activeCategory, () => {
  loadFiles();
});

onMounted(() => {
  onRefresh();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Card size="small">
        <Statistic
          :title="$t('admin.system.systemLog.totalFiles')"
          :value="stats?.totalFiles ?? 0"
          :loading="statsLoading"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:file-text" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
      <Card size="small">
        <Statistic
          :title="$t('admin.system.systemLog.totalSize')"
          :value="stats?.totalSizeFormatted ?? '-'"
          :loading="statsLoading"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:hard-drive" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
      <Card size="small">
        <Statistic
          :title="$t('admin.system.systemLog.categories')"
          :value="categories.length"
          :loading="loading"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:folder" class="mr-1 text-primary" />
          </template>
        </Statistic>
      </Card>
    </div>

    <!-- 主内容区 -->
    <div class="flex flex-1 gap-4 overflow-hidden">
      <!-- 左侧：分类和文件列表 -->
      <Card
        class="w-[400px] flex-shrink-0 overflow-hidden"
        :body-style="{
          padding: 0,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }"
      >
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:folder-tree" class="text-primary" />
            {{ $t('admin.system.systemLog.files') }}
          </div>
        </template>
        <template #extra>
          <Button
            type="text"
            size="small"
            :loading="loading"
            @click="onRefresh"
          >
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" />
            </template>
          </Button>
        </template>

        <Spin :spinning="loading" class="flex-1 overflow-hidden">
          <!-- 分类 Tabs -->
          <Tabs
            v-if="categories.length > 0"
            v-model:active-key="activeCategory"
            type="card"
            size="small"
            class="h-full [&_.ant-tabs-content]:h-full [&_.ant-tabs-content]:overflow-auto"
          >
            <TabPane v-for="cat in categories" :key="cat.name" :tab="cat.name">
              <template #tab>
                <span class="flex items-center gap-1">
                  {{ cat.name }}
                  <Tag size="small" color="blue">{{ cat.fileCount }}</Tag>
                </span>
              </template>

              <!-- 文件列表 -->
              <List
                v-if="files.length > 0"
                :data-source="files"
                size="small"
                class="px-2"
              >
                <template #renderItem="{ item }">
                  <ListItem
                    class="cursor-pointer transition-colors hover:bg-gray-50"
                    :class="{
                      'bg-primary/5': selectedFile?.filename === item.filename,
                    }"
                    @click="onSelectFile(item)"
                  >
                    <ListItemMeta>
                      <template #title>
                        <div class="flex items-center gap-2">
                          <IconifyIcon
                            icon="lucide:file-text"
                            class="text-gray-400"
                          />
                          <span class="truncate text-sm">{{
                            item.filename
                          }}</span>
                        </div>
                      </template>
                      <template #description>
                        <div
                          class="flex items-center gap-3 text-xs text-gray-400"
                        >
                          <span>{{ item.sizeFormatted }}</span>
                          <span>{{ formatDate(item.modifiedAt) }}</span>
                        </div>
                      </template>
                    </ListItemMeta>
                    <template #actions>
                      <Tooltip :title="$t('admin.system.systemLog.download')">
                        <Button
                          v-access:code="['system_log:download']"
                          type="text"
                          size="small"
                          @click.stop="onDownload(item)"
                        >
                          <template #icon>
                            <IconifyIcon icon="lucide:download" />
                          </template>
                        </Button>
                      </Tooltip>
                      <Popconfirm
                        :title="
                          $t('admin.system.systemLog.messages.deleteConfirm', {
                            name: item.filename,
                          })
                        "
                        :ok-text="$t('shared.common.confirm')"
                        :cancel-text="$t('shared.common.cancel')"
                        :ok-button-props="{ danger: true }"
                        @confirm="onDelete(item)"
                      >
                        <Tooltip :title="$t('admin.system.systemLog.delete')">
                          <Button
                            v-access:code="['system_log:delete']"
                            type="text"
                            size="small"
                            danger
                            @click.stop
                          >
                            <template #icon>
                              <IconifyIcon icon="lucide:trash-2" />
                            </template>
                          </Button>
                        </Tooltip>
                      </Popconfirm>
                    </template>
                  </ListItem>
                </template>
              </List>
              <Empty
                v-else
                :description="$t('admin.system.systemLog.noFiles')"
                class="py-8"
              />
            </TabPane>
          </Tabs>
          <Empty
            v-else
            :description="$t('admin.system.systemLog.noFiles')"
            class="py-8"
          />
        </Spin>
      </Card>

      <!-- 右侧：日志内容 -->
      <Card
        class="flex-1 overflow-hidden"
        :body-style="{
          padding: '12px',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }"
      >
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:file-code" class="text-primary" />
            {{ $t('admin.system.systemLog.content') }}
            <span v-if="selectedFile" class="text-sm font-normal text-gray-500">
              - {{ selectedFile.filename }}
            </span>
          </div>
        </template>

        <Spin :spinning="contentLoading" class="flex-1 overflow-hidden">
          <template v-if="logContent">
            <pre
              class="h-full overflow-auto whitespace-pre-wrap break-all rounded bg-gray-900 p-4 font-mono text-xs text-green-400"
              >{{ logContent.lines.join('\n') }}</pre
            >
            <div v-if="logContent.hasMore" class="mt-2 text-center">
              <Button type="link" :loading="contentLoading" @click="onLoadMore">
                {{ $t('admin.system.systemLog.loadMore') }}
              </Button>
            </div>
            <div v-else class="mt-2 text-center text-xs text-gray-400">
              {{ $t('admin.system.systemLog.allLoaded') }}
            </div>
          </template>
          <Empty
            v-else
            :description="$t('admin.system.systemLog.noContent')"
            class="flex h-full items-center justify-center"
          />
        </Spin>
      </Card>
    </div>
  </Page>
</template>
