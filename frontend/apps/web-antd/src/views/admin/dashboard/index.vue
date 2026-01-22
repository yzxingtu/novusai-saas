<script lang="ts" setup>
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { useUserStore } from '@vben/stores';

import { Button, Card } from 'ant-design-vue';

import { IconPicker } from '#/components/business/icon-picker';

const userStore = useUserStore();

// 图标选择器弹窗
const iconPickerOpen = ref(false);

function onIconSelect(icon: string) {
  // eslint-disable-next-line no-console
  console.log('选中图标:', icon);
}
</script>

<template>
  <div class="p-5">
    <!-- 图标选择器弹窗 -->
    <IconPicker v-model:open="iconPickerOpen" @select="onIconSelect" />

    <Card title="平台管理控制台" class="mb-4">
      <template #extra>
        <Button type="primary" ghost @click="iconPickerOpen = true">
          <IconifyIcon icon="lucide:palette" class="mr-1.5" />
          图标库
        </Button>
      </template>
      <div class="text-lg">
        您好，{{ userStore.userInfo?.realName || '管理员' }}！
      </div>
      <p class="mt-2 text-gray-500">
        这是平台管理端控制台，您可以在这里管理平台的各项配置。
      </p>
    </Card>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <template #title>
          <span class="text-primary">租户总数</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-success">活跃租户</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-warning">用户总数</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
      <Card>
        <template #title>
          <span class="text-primary/80">今日登录</span>
        </template>
        <div class="text-3xl font-bold">--</div>
      </Card>
    </div>
  </div>
</template>
