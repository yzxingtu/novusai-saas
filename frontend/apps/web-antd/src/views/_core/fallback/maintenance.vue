<script lang="ts" setup>
/**
 * 系统维护页面
 *
 * 当平台配置 maintenance_mode=true 时，路由守卫将所有非登录请求重定向到此页面。
 * 显示后端配置的维护提示信息（maintenance_message）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button } from 'ant-design-vue';

import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store';

defineOptions({ name: 'MaintenancePage' });

const publicConfigStore = usePublicConfigStore();

const maintenanceMessage = computed(() => {
  return (
    publicConfigStore.tenantConfig?.maintenance?.message ||
    publicConfigStore.platformConfig?.maintenance?.message ||
    $t('common.maintenance.defaultMessage')
  );
});

const siteName = computed(() => {
  return (
    publicConfigStore.tenantConfig?.brand?.siteName ||
    publicConfigStore.platformConfig?.brand?.siteName ||
    import.meta.env.VITE_APP_TITLE ||
    'NovusAI'
  );
});

const refreshInterval = ref<ReturnType<typeof setInterval>>();

async function refreshMaintenanceStatus() {
  await publicConfigStore.detectDomainType().catch(() => {});

  if (publicConfigStore.isDomainTenantDomain) {
    publicConfigStore.resetTenantConfig();
    const config = await publicConfigStore.loadTenantConfig({
      skipDomainCheck: true,
    });
    if (config && !config.maintenance.enabled) {
      window.location.reload();
    }
    return;
  }

  publicConfigStore.resetPlatformConfig();
  const config = await publicConfigStore.loadPlatformConfig();
  if (config && !config.maintenance.enabled) {
    window.location.reload();
  }
}

onMounted(() => {
  void publicConfigStore.detectDomainType().catch(() => {});
  refreshInterval.value = setInterval(() => {
    void refreshMaintenanceStatus();
  }, 30_000);
});

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value);
  }
});

function handleRefresh() {
  window.location.reload();
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-background p-4">
    <div class="flex max-w-lg flex-col items-center gap-6 text-center">
      <!-- 图标 -->
      <div
        class="flex size-24 items-center justify-center rounded-3xl bg-warning/10"
      >
        <IconifyIcon icon="lucide:hard-hat" class="size-12 text-warning" />
      </div>

      <!-- 标题 -->
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-bold text-foreground">
          {{ $t('common.maintenance.title') }}
        </h1>
        <p class="text-base leading-relaxed text-muted-foreground">
          {{ maintenanceMessage }}
        </p>
      </div>

      <!-- 站点名 -->
      <p class="text-sm text-muted-foreground/60">— {{ siteName }}</p>

      <!-- 刷新按钮 -->
      <Button type="primary" @click="handleRefresh">
        <template #icon>
          <IconifyIcon icon="lucide:refresh-cw" />
        </template>
        {{ $t('common.maintenance.refresh') }}
      </Button>
    </div>
  </div>
</template>
