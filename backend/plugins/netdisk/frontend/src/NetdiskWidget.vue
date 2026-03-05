<script lang="ts" setup>
import { ref, onMounted, computed } from 'vue';

const getShared = () =>
  (window as unknown as { NovusPluginShared?: {
    $t?: (k: string) => string;
    useRouter?: () => { push: (path: string) => void };
  } }).NovusPluginShared;

const $t = (key: string) => getShared()?.$t?.(key) ?? key.split('.').pop() ?? key;

const quotaPercent = ref(0);

const showBadge = computed(() => quotaPercent.value >= 90);

function navigate() {
  const shared = getShared();
  if (shared?.useRouter) {
    shared.useRouter().push('/tenant/plugins/netdisk');
  } else {
    window.location.href = '/tenant/plugins/netdisk';
  }
}

onMounted(async () => {
  try {
    const shared = getShared();
    if (!shared) return;
    const client = (shared as unknown as { requestClient?: { get: <T>(url: string) => Promise<T> } }).requestClient;
    if (!client) return;
    const r = await client.get<{ data: { usedPercent?: number } }>('/tenant/plugins/netdisk/api/quota');
    quotaPercent.value = r.data?.usedPercent ?? 0;
  } catch {
    quotaPercent.value = 0;
  }
});
</script>

<template>
  <a-tooltip :title="$t('plugin.netdisk.name')" placement="bottom">
    <div
      class="relative flex items-center justify-center w-9 h-9 rounded-md cursor-pointer transition-colors"
      @click="navigate"
    >
      <!-- 硬盘图标 -->
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-foreground">
        <line x1="22" y1="12" x2="2" y2="12"/>
        <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>
        <line x1="6" y1="16" x2="6.01" y2="16"/>
        <line x1="10" y1="16" x2="10.01" y2="16"/>
      </svg>
      <!-- 存储告警角标（使用率 >= 90%）-->
      <span
        v-if="showBadge"
        class="absolute top-1 right-1 w-[7px] h-[7px] rounded-full bg-red-500"
      />
    </div>
  </a-tooltip>
</template>
