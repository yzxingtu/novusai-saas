<script lang="ts" setup>
import { onMounted, ref } from 'vue';

import { useUserStore } from '@vben/stores';

import { Card, Spin } from 'ant-design-vue';

import { type TenantDashboardStats, getTenantDashboardStatsApi } from '#/api/tenant/dashboard';
import { $t } from '#/locales';

defineOptions({ name: 'TenantDashboard' });

const userStore = useUserStore();
const loading = ref(false);
const stats = ref<TenantDashboardStats>({
  total_users: 0,
  active_users: 0,
  api_calls: 0,
  resource_usage: 0,
});

async function loadStats() {
  loading.value = true;
  try {
    stats.value = await getTenantDashboardStatsApi();
  } catch {
    // error handled by global interceptor
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadStats();
});
</script>

<template>
  <div class="p-5">
    <Card :title="$t('tenant.dashboard.title')" class="mb-4">
      <template #extra>
        <span class="text-muted-foreground">{{ $t('tenant.dashboard.welcome') }}</span>
      </template>
      <div class="text-lg">
        {{
          $t('tenant.dashboard.greeting', {
            name: userStore.userInfo?.realName || $t('tenant.common.admin'),
          })
        }}
      </div>
      <p class="mt-2 text-muted-foreground">
        {{ $t('tenant.dashboard.description') }}
      </p>
    </Card>

    <Spin :spinning="loading">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <template #title>
            <span class="text-primary">{{
              $t('tenant.dashboard.stats.totalUsers')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.total_users }}</div>
        </Card>
        <Card>
          <template #title>
            <span class="text-success">{{
              $t('tenant.dashboard.stats.activeUsers')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.active_users }}</div>
        </Card>
        <Card>
          <template #title>
            <span class="text-warning">{{
              $t('tenant.dashboard.stats.apiCalls')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.api_calls }}</div>
        </Card>
        <Card>
          <template #title>
            <span class="text-primary/80">{{
              $t('tenant.dashboard.stats.resourceUsage')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.resource_usage }}</div>
        </Card>
      </div>
    </Spin>
  </div>
</template>
