<script lang="ts" setup>
import type { AIHealthStatus } from '#/api/admin/ai';

/**
 * AI 供应商健康状态监控页面 — useCrudList + autoRefresh
 */
import { computed, ref, watchEffect } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Badge, Button, Card, Empty, Spin, Tag, Tooltip } from 'ant-design-vue';

import { getAIHealthStatusApi } from '#/api/admin/ai';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import { toAttachmentImageUrl } from '#/utils/image';

import AIGatewayQuickStartHero from '../_shared/AIGatewayQuickStartHero.vue';

defineOptions({ name: 'AIHealthMonitor' });

// ========== 声明式列表管理 + 30秒自动刷新 / Declarative list + 30s refresh ==========
const healthSummary = ref({ degraded: 0, healthy: 0, unavailable: 0 });

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
  ai: {
    entityName: $t('admin.ai.health.name'),
    entityDescription: $t('admin.ai.health.entityDescription'),
    contextExtras: () => ({
      healthy: healthSummary.value.healthy,
      degraded: healthSummary.value.degraded,
      unavailable: healthSummary.value.unavailable,
    }),
  },
});

// ========== 概览计数 / Overview counts ==========
watchEffect(() => {
  const all = statuses.value;
  healthSummary.value = {
    healthy: all.filter((s) => s.is_healthy && s.is_available).length,
    degraded: all.filter((s) => !s.is_healthy && s.is_available).length,
    unavailable: all.filter((s) => !s.is_available).length,
  };
});

const healthyCount = computed(
  () => statuses.value.filter((s) => s.is_healthy && s.is_available).length,
);
const degradedCount = computed(
  () => statuses.value.filter((s) => !s.is_healthy && s.is_available).length,
);
const unavailableCount = computed(
  () => statuses.value.filter((s) => !s.is_available).length,
);

// ========== 辅助 / Helpers ==========
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
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4 !p-4">
    <AIGatewayQuickStartHero :current-title="$t('admin.ai.health.title')" />

    <section
      class="rounded-[20px] border border-border/70 bg-card px-4 py-3 shadow-sm"
    >
      <div
        class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"
      >
        <div class="flex flex-wrap items-center gap-2">
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-700 dark:text-emerald-200"
          >
            <Badge status="success" />
            {{ healthyCount }} {{ $t('admin.ai.health.status.healthy') }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs text-amber-700 dark:text-amber-200"
          >
            <Badge status="warning" />
            {{ degradedCount }} {{ $t('admin.ai.health.status.degraded') }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-2.5 py-1 text-xs text-rose-700 dark:text-rose-200"
          >
            <Badge status="error" />
            {{ unavailableCount }}
            {{ $t('admin.ai.health.status.unavailable') }}
          </span>
          <span
            class="rounded-xl border border-border/60 bg-background/80 px-3 py-2 text-xs text-muted-foreground"
          >
            <span class="mr-1 font-semibold text-foreground">
              {{ statuses.length }}
            </span>
            {{ $t('admin.ai.health.providers') }}
          </span>
        </div>
        <Button size="small" @click="loadHealth">
          <template #icon>
            <IconifyIcon icon="lucide:refresh-cw" class="size-3.5" />
          </template>
          {{ $t('admin.ai.health.refresh') }}
        </Button>
      </div>
    </section>

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
                class="flex size-10 items-center justify-center overflow-hidden rounded-lg"
                :class="
                  status.is_available ? 'bg-success/10' : 'bg-destructive/10'
                "
              >
                <img
                  v-if="
                    toAttachmentImageUrl(status.provider_icon, {
                      preset: 'small',
                    })
                  "
                  :src="
                    toAttachmentImageUrl(status.provider_icon, {
                      preset: 'small',
                    })
                  "
                  class="size-full object-contain"
                  alt=""
                />
                <IconifyIcon
                  v-else
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
