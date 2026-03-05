<script lang="ts" setup>
/**
 * N14d: 底部状态栏 — 已选数量 + 配额进度条
 * 配额 >90% 显示警告色，>99% 显示危险色
 */
interface QuotaInfo {
  quotaBytes:  number;
  usedBytes:   number;
  freeBytes:   number;
  usedPercent: number;
}

interface Props {
  selectedCount: number;
  quota:         QuotaInfo | null;
}

const props = defineProps<Props>();

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

function fmtBytes(bytes: number): string {
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function quotaColor(pct: number): string {
  if (pct >= 99) return '#ef4444';
  if (pct >= 90) return '#f59e0b';
  return '#22c55e';
}

function quotaStatus(pct: number): 'exception' | 'normal' {
  return pct >= 99 ? 'exception' : 'normal';
}

function quotaLabel(q: QuotaInfo): string {
  return `${fmtBytes(q.usedBytes)} / ${fmtBytes(q.quotaBytes)}`;
}
</script>

<template>
  <div class="flex items-center justify-between py-1 px-4 border-t border-border bg-background shrink-0 min-h-[32px] text-xs text-muted-foreground gap-4">
    <!-- 已选提示 -->
    <span class="min-w-[80px]">
      <span v-if="selectedCount > 0">{{ $t('plugin.netdisk.action.selected').replace('{count}', String(selectedCount)) }}</span>
    </span>

    <!-- 配额进度条 -->
    <div v-if="quota" class="flex items-center gap-2 flex-1 max-w-[280px] ml-auto">
      <span class="whitespace-nowrap text-[11px]">{{ quotaLabel(quota) }}</span>
      <a-progress
        :percent="Math.min(quota.usedPercent, 100)"
        :show-info="false"
        :stroke-color="quotaColor(quota.usedPercent)"
        :status="quotaStatus(quota.usedPercent)"
        size="small"
        class="flex-1 !m-0"
      />
      <span :style="{ color: quotaColor(quota.usedPercent), fontWeight: quota.usedPercent >= 90 ? 600 : 400, whiteSpace: 'nowrap', fontSize: '11px' }">
        {{ quota.usedPercent.toFixed(1) }}%
      </span>
    </div>
  </div>
</template>
