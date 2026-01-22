<script lang="ts" setup>
import { useUserStore } from '@vben/stores';

import { Card } from 'ant-design-vue';

import { $t } from '#/locales';

const userStore = useUserStore();
</script>

<template>
  <div class="p-5">
    <Card :title="$t('tenant.dashboard.title')" class="mb-4">
      <template #extra>
        <span class="text-gray-500">{{ $t('tenant.dashboard.welcome') }}</span>
      </template>
      <div class="text-lg">
        {{
          $t('tenant.dashboard.greeting', {
            name: userStore.userInfo?.realName || $t('tenant.common.admin'),
          })
        }}
      </div>
      <p class="mt-2 text-gray-500">
        {{ $t('tenant.dashboard.description') }}
      </p>
    </Card>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <template #title>
          <span class="text-primary">{{
            $t('tenant.dashboard.stats.totalUsers')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-success">{{
            $t('tenant.dashboard.stats.activeUsers')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-warning">{{
            $t('tenant.dashboard.stats.apiCalls')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-primary/80">{{
            $t('tenant.dashboard.stats.resourceUsage')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
    </div>
  </div>
</template>
