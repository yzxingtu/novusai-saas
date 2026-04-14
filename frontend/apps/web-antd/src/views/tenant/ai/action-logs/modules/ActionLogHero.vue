<script lang="ts" setup>
import type { ActionLogStats } from '#/api/tenant/action-logs';

import { computed, onMounted, ref } from 'vue';

import { getActionLogStatsApi } from '#/api/tenant/action-logs';
import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { $t } from '#/locales';

defineOptions({ name: 'ActionLogHero' });

const stats = ref<ActionLogStats>({
  total: 0,
  success_count: 0,
  failed_count: 0,
  rejected_count: 0,
  pending_count: 0,
  level_read: 0,
  level_safe_write: 0,
  level_dangerous: 0,
  avg_duration_ms: null,
});

async function loadStats() {
  try {
    stats.value = await getActionLogStatsApi();
  } catch {
    // ignore / 忽略统计拉取失败
  }
}

const successRate = computed(() => {
  const total = stats.value.total;
  if (total === 0) {
    return '-';
  }

  return `${((stats.value.success_count / total) * 100).toFixed(1)}%`;
});

const heroMetrics = computed(() => [
  {
    key: 'total',
    label: $t('tenant.ai.actionLog.stats.totalActions'),
    value: stats.value.total,
  },
  {
    key: 'successRate',
    label: $t('tenant.ai.actionLog.stats.successRate'),
    value: successRate.value,
  },
  {
    key: 'rejected',
    label: $t('tenant.ai.actionLog.stats.rejectedCount'),
    value: stats.value.rejected_count,
  },
  {
    key: 'failed',
    label: $t('tenant.ai.actionLog.status_options.failed'),
    value: stats.value.failed_count,
  },
]);

const heroChips = computed(() => [
  {
    key: 'audit',
    icon: 'lucide:shield-check',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('tenant.ai.actionLog.actionType')} / ${$t('tenant.ai.actionLog.status')} / ${$t('tenant.ai.actionLog.executionTime')}`,
  },
  {
    key: 'levels',
    icon: 'lucide:badge-alert',
    className: 'bg-background/90 text-foreground',
    text: `${stats.value.level_read}/${stats.value.level_safe_write}/${stats.value.level_dangerous}`,
  },
]);

onMounted(() => {
  void loadStats();
});
</script>

<template>
  <AIPageHeroCard
    :chips="heroChips"
    :description="$t('tenant.ai.actionLog.pageDesc')"
    icon="lucide:shield-check"
    icon-wrap-class="bg-primary/10 text-primary"
    :metrics="heroMetrics"
    :title="$t('tenant.ai.actionLog.title')"
  />
</template>
