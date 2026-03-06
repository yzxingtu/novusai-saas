<script lang="ts" setup>
import type { AIHealthStatus } from '#/api/admin/ai';

/**
 * AI 供应商健康状态监控页面 — useCrudList + autoRefresh
 */
import { computed, onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Badge, Button, Card, Empty, Spin, Tag, Tooltip } from 'ant-design-vue';

import { getAIHealthStatusApi } from '#/api/admin/ai';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';

defineOptions({ name: 'AIHealthMonitor' });

// ========== 声明式列表管理 + 30秒自动刷新 ==========
const {
  list: statuses,
  loading,
  loadList: loadHealth,
} = useCrudList<AIHealthStatus>({
  api: {
    list: () =>
      getAIHealthStatusApi() as unknown as Promise<{
        items: AIHealthStatus[];
        total: number;
      }>,
    resource: '/admin/ai/health',
  },
  keyField: 'provider_id',
  i18nPrefix: 'admin.ai.health',
  pager: false,
  autoRefreshInterval: 30_000,
});

// ========== 概览计数 ==========
const healthyCount = computed(
  () => statuses.value.filter((s) => s.is_healthy && s.is_available).length,
);
const degradedCount = computed(
  () => statuses.value.filter((s) => !s.is_healthy && s.is_available).length,
);
const unavailableCount = computed(
  () => statuses.value.filter((s) => !s.is_available).length,
);

// ========== 辅助 ==========
function getStatusColor(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available) return 'success';
  if (!status.is_healthy && status.is_available) return 'warning';
  return 'error';
}

function getStatusText(status: AIHealthStatus): string {
  if (status.is_healthy && status.is_available)
    return $t('admin.ai.health.status.healthy');
  if (!status.is_healthy && status.is_available)
    return $t('admin.ai.health.status.degraded');
  return $t('admin.ai.health.status.unavailable');
}

function getBadgeStatus(
  status: AIHealthStatus,
): 'error' | 'success' | 'warning' {
  return getStatusColor(status) as 'error' | 'success' | 'warning';
}

const cleanupPageContext = registerPageContext('admin/ai/health', () => ({
  page_key: 'admin.ai.health',
  page_title: $t('admin.ai.health.name'),
  page_data: {
    resource: '/admin/ai/health',
    healthy: healthyCount.value,
    degraded: degradedCount.value,
    unavailable: unavailableCount.value,
  },
}));

onUnmounted(cleanupPageContext);
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.health.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 顶部操作栏 -->
    <Card :body-style="{ padding: '12px 16px' }">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-2">
            <IconifyIcon
              icon="lucide:heart-pulse"
              class="size-5 text-primary"
            />
            <span class="font-medium text-foreground">{{
              $t('admin.ai.health.title')
            }}</span>
          </div>
          <!-- 概览摘要 -->
          <div class="flex items-center gap-2 text-sm">
            <span
              v-if="healthyCount > 0"
              class="flex items-center gap-1 text-success"
            >
              <Badge status="success" />
              {{ healthyCount }} {{ $t('admin.ai.health.status.healthy') }}
            </span>
            <span
              v-if="degradedCount > 0"
              class="flex items-center gap-1 text-warning"
            >
              <Badge status="warning" />
              {{ degradedCount }} {{ $t('admin.ai.health.status.degraded') }}
            </span>
            <span
              v-if="unavailableCount > 0"
              class="flex items-center gap-1 text-destructive"
            >
              <Badge status="error" />
              {{ unavailableCount }}
              {{ $t('admin.ai.health.status.unavailable') }}
            </span>
          </div>
        </div>
        <Button size="small" @click="loadHealth">
          <template #icon>
            <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
          </template>
          {{ $t('admin.ai.health.refresh') }}
        </Button>
      </div>
    </Card>

    <!-- 健康状态卡片网格 -->
    <Spin :spinning="loading">
      <div
        v-if="statuses.length > 0"
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <Card
          v-for="status in statuses"
          :key="status.provider_id"
          class="transition-shadow duration-200 hover:shadow-md"
          :body-style="{ padding: '20px' }"
        >
          <!-- 头部：供应商 + 状态 -->
          <div class="mb-4 flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div
                class="flex size-10 items-center justify-center rounded-lg"
                :class="
                  status.is_available ? 'bg-success/10' : 'bg-destructive/10'
                "
              >
                <IconifyIcon
                  icon="lucide:cpu"
                  class="size-5"
                  :class="
                    status.is_available ? 'text-success' : 'text-destructive'
                  "
                />
              </div>
              <div>
                <div class="font-medium text-foreground">
                  {{ status.provider_name }}
                </div>
                <code class="text-xs text-muted-foreground">{{
                  status.provider_code
                }}</code>
              </div>
            </div>
            <Badge
              :status="getBadgeStatus(status)"
              :text="getStatusText(status)"
            />
          </div>

          <!-- 指标 -->
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.responseTime')
              }}</span>
              <div class="mt-0.5 font-medium text-foreground">
                <span
                  :class="
                    status.response_time_ms > 5000
                      ? 'text-destructive'
                      : status.response_time_ms > 3000
                        ? 'text-warning'
                        : ''
                  "
                >
                  {{ status.response_time_ms }}ms
                </span>
              </div>
            </div>
            <div>
              <span class="text-muted-foreground">{{
                $t('admin.ai.health.failures')
              }}</span>
              <div class="mt-0.5 font-medium">
                <Tag v-if="status.consecutive_failures === 0" color="success">
                  0
                </Tag>
                <Tag
                  v-else
                  :color="
                    status.consecutive_failures >= 3 ? 'error' : 'warning'
                  "
                >
                  {{ status.consecutive_failures }}
                </Tag>
              </div>
            </div>
          </div>

          <!-- 错误信息 -->
          <div v-if="status.error_message" class="mt-3">
            <Tooltip :title="status.error_message">
              <div
                class="line-clamp-1 rounded bg-destructive/5 px-2 py-1 text-xs text-destructive"
              >
                {{ status.error_message }}
              </div>
            </Tooltip>
          </div>

          <!-- 最后检查时间 -->
          <div class="mt-3 text-xs text-muted-foreground">
            {{ $t('admin.ai.health.lastCheck') }}:
            {{ formatDate(status.checked_at) }}
          </div>
        </Card>
      </div>
      <Empty v-else class="py-16" :description="$t('admin.ai.health.noData')" />
    </Spin>
  </Page>
</template>
