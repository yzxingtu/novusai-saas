<script lang="ts" setup>
/**
 * 智能体管理列表页面（平台端）
 * - 顶部统计卡片（总数、已发布、草稿、已禁用）
 * - 支持状态切换操作
 */
import type { AIAgentInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIAgentList' });

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Modal, Spin, Tag } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAIAgentListApi, updateAIAgentStatusApi } from '#/api/admin/ai';
import { $t } from '#/locales';

import {
  getExecutionModeText,
  getStatusText,
  useColumns,
  useGridFormSchema,
} from './data';

// ============================================================
// Summary statistics
// ============================================================

interface AgentStats {
  total: number;
  published: number;
  draft: number;
  disabled: number;
}

const statsLoading = ref(false);
const statsData = ref<AgentStats>({
  total: 0,
  published: 0,
  draft: 0,
  disabled: 0,
});

const summaryCards = computed(() => [
  {
    key: 'total',
    label: $t('admin.ai.agent.summary.total'),
    value: statsData.value.total,
    icon: 'lucide:bot',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'published',
    label: $t('admin.ai.agent.summary.published'),
    value: statsData.value.published,
    icon: 'lucide:check-circle',
    bgClass: 'bg-success/10',
    iconClass: 'text-success',
  },
  {
    key: 'draft',
    label: $t('admin.ai.agent.summary.draft'),
    value: statsData.value.draft,
    icon: 'lucide:file-edit',
    bgClass: 'bg-primary/10',
    iconClass: 'text-primary',
  },
  {
    key: 'disabled',
    label: $t('admin.ai.agent.summary.disabled'),
    value: statsData.value.disabled,
    icon: 'lucide:ban',
    bgClass: 'bg-destructive/10',
    iconClass: 'text-destructive',
  },
]);

async function loadStats() {
  statsLoading.value = true;
  try {
    const [allRes, publishedRes, draftRes, disabledRes] = await Promise.all([
      getAIAgentListApi({ 'page[number]': 1, 'page[size]': 1 }),
      getAIAgentListApi({ 'page[number]': 1, 'page[size]': 1, 'filter[status][eq]': 'published' }),
      getAIAgentListApi({ 'page[number]': 1, 'page[size]': 1, 'filter[status][eq]': 'draft' }),
      getAIAgentListApi({ 'page[number]': 1, 'page[size]': 1, 'filter[status][eq]': 'disabled' }),
    ]);
    statsData.value = {
      total: allRes.total,
      published: publishedRes.total,
      draft: draftRes.total,
      disabled: disabledRes.total,
    };
  } catch {
    // Error handled by request interceptor
  } finally {
    statsLoading.value = false;
  }
}

onMounted(loadStats);

// ============================================================
// Status toggle
// ============================================================

function getNextStatus(current: string): string {
  switch (current) {
    case 'draft': return 'published';
    case 'published': return 'disabled';
    case 'disabled': return 'published';
    default: return 'published';
  }
}

function onToggleStatus(row: AIAgentInfo) {
  const nextStatus = getNextStatus(row.status);
  const isDisabling = nextStatus === 'disabled';
  Modal.confirm({
    title: isDisabling
      ? $t('admin.ai.agent.messages.confirmDisable')
      : $t('admin.ai.agent.messages.confirmPublish'),
    onOk: async () => {
      try {
        await updateAIAgentStatusApi(row.id, nextStatus);
        message.success($t('admin.ai.agent.messages.toggleSuccess'));
        onRefresh();
        loadStats();
      } catch {
        // Error handled by request interceptor
      }
    },
  });
}

// ============================================================
// CRUD Grid
// ============================================================

const { Grid, onRefresh } = useCrudPage<AIAgentInfo>({
  api: {
    list: getAIAgentListApi,
    resource: '/admin/ai/agents',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  i18nPrefix: 'admin.ai.agent',
  defaultSort: '-created_at',
  customActions: {
    toggleStatus: (row) => onToggleStatus(row),
  },
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <!-- Summary statistics cards -->
    <Spin :spinning="statsLoading">
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card
          v-for="stat in summaryCards"
          :key="stat.key"
          :body-style="{ padding: '16px' }"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex size-10 items-center justify-center rounded-lg"
              :class="stat.bgClass"
            >
              <IconifyIcon
                :icon="stat.icon"
                class="size-5"
                :class="stat.iconClass"
              />
            </div>
            <div>
              <div class="text-sm text-muted-foreground">{{ stat.label }}</div>
              <div class="text-lg font-semibold text-foreground">
                {{ stat.value }}
              </div>
            </div>
          </div>
        </Card>
      </div>
    </Spin>

    <!-- Data table -->
    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <IconifyIcon
              icon="lucide:bot"
              class="size-4 text-primary"
            />
            <span class="font-medium text-foreground">
              {{ row.name }}
            </span>
          </div>
          <div
            v-if="row.description"
            class="mt-0.5 truncate text-xs text-muted-foreground"
          >
            {{ row.description }}
          </div>
        </template>

        <!-- 状态列 -->
        <template #status_cell="{ row }">
          <Tag
            :color="
              row.status === 'published'
                ? 'success'
                : row.status === 'disabled'
                  ? 'error'
                  : 'default'
            "
          >
            {{ getStatusText(row.status) }}
          </Tag>
        </template>

        <!-- 执行模式列 -->
        <template #mode_cell="{ row }">
          <Tag color="blue">
            {{ getExecutionModeText(row.execution_mode) }}
          </Tag>
        </template>

        <!-- 模型名称列 -->
        <template #modelName_cell="{ row }">
          <div v-if="row.model_name" class="flex items-center gap-1.5">
            <IconifyIcon
              icon="lucide:brain"
              class="size-3.5 text-muted-foreground"
            />
            <code class="rounded bg-accent px-1 py-0.5 text-xs">
              {{ row.model_name }}
            </code>
          </div>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 版本列 -->
        <template #version_cell="{ row }">
          <span
            v-if="row.published_version"
            class="font-mono text-sm text-foreground"
          >
            v{{ row.published_version }}
          </span>
          <span v-else class="text-muted-foreground">-</span>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
