<script lang="ts" setup>
import { onMounted, ref } from 'vue';

import { useUserStore } from '@vben/stores';

import { Card, Spin } from 'ant-design-vue';

import { type DashboardStats, getDashboardStatsApi } from '#/api/admin/dashboard';
import { $t } from '#/locales';

defineOptions({ name: 'Dashboard' });

const userStore = useUserStore();
const loading = ref(false);
const stats = ref<DashboardStats>({
  total_tenants: 0,
  active_tenants: 0,
  total_users: 0,
  today_login: 0,
});

async function loadStats() {
  loading.value = true;
  try {
    stats.value = await getDashboardStatsApi();
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
    <Card :title="$t('admin.dashboard.platformConsole')" class="mb-4">
      <template #extra>
        <span class="text-muted-foreground">{{ $t('admin.dashboard.welcome') }}</span>
      </template>
      <div class="text-lg">
        {{
          $t('admin.dashboard.greeting', {
            name: userStore.userInfo?.realName || $t('admin.dashboard.admin'),
          })
        }}
      </div>
      <p class="mt-2 text-gray-500">
        {{ $t('admin.dashboard.description') }}
      </p>
    </Card>

    <Spin :spinning="loading">
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <template #title>
            <span class="text-primary">{{
              $t('admin.dashboard.stats.totalTenants')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.total_tenants }}</div>
        </Card>
        <Card>
          <template #title>
            <span class="text-success">{{
              $t('admin.dashboard.stats.activeTenants')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.active_tenants }}</div>
        </Card>
        <Card>
          <template #title>
            <span class="text-warning">{{
              $t('admin.dashboard.stats.totalUsers')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.total_users }}</div>
        </Card>
        <Card>
          <template #title>
            <span class="text-primary/80">{{
              $t('admin.dashboard.stats.todayLogin')
            }}</span>
          </template>
          <div class="text-3xl font-bold">{{ stats.today_login }}</div>
        </Card>
      </div>
    </Spin>
  </div>
</template>
