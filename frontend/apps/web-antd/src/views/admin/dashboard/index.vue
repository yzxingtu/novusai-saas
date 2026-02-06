<script lang="ts" setup>
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { useUserStore } from '@vben/stores';

import { Button, Card } from 'ant-design-vue';

import { IconPicker } from '#/components/business/icon-picker';
import { $t } from '#/locales';

defineOptions({ name: 'Dashboard' });

const userStore = useUserStore();

// 图标选择器弹窗
const iconPickerOpen = ref(false);

function onIconSelect(_icon: string) {
  //
}
</script>

<template>
  <div class="p-5">
    <!-- 图标选择器弹窗 -->
    <IconPicker v-model:open="iconPickerOpen" @select="onIconSelect" />

    <Card :title="$t('admin.dashboard.platformConsole')" class="mb-4">
      <template #extra>
        <Button type="primary" ghost @click="iconPickerOpen = true">
          <IconifyIcon icon="lucide:palette" class="mr-1.5" />
          {{ $t('admin.dashboard.iconLibrary') }}
        </Button>
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

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <template #title>
          <span class="text-primary">{{
            $t('admin.dashboard.stats.totalTenants')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-success">{{
            $t('admin.dashboard.stats.activeTenants')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-warning">{{
            $t('admin.dashboard.stats.totalUsers')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-primary/80">{{
            $t('admin.dashboard.stats.todayLogin')
          }}</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
    </div>
  </div>
</template>
