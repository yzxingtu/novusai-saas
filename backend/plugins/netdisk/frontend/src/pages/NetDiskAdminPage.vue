<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import {
  adminGetStatsApi, adminListQuotasApi, adminListSharesApi,
  adminRevokeShareApi, adminUpdateQuotaApi,
} from '../api/netdisk';

interface QuotaRow { tenantId: number; quotaBytes: number; usedBytes: number; usedPercent: number; }

const stats   = ref<Record<string, number>>({});
const quotas  = ref<QuotaRow[]>([]);
const shares  = ref<Record<string, unknown>[]>([]);
const loading = ref(false);

const activeTab = ref<'quotas' | 'shares'>('quotas');

// 配额更新弹窗
const quotaModal       = ref(false);
const quotaTarget      = ref<QuotaRow | null>(null);
const quotaInputGb     = ref(10);
const quotaSaving      = ref(false);

const $t = (key: string) => {
  const shared = (window as unknown as { NovusPluginShared?: { $t?: (k: string) => string } }).NovusPluginShared;
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
};

async function loadStats() {
  try {
    const r = await adminGetStatsApi();
    stats.value = r.data ?? {};
  } catch { /* ignore */ }
}

async function loadQuotas() {
  loading.value = true;
  try {
    const r = await adminListQuotasApi(1, 100) as { data: { items: QuotaRow[] } };
    quotas.value = r.data?.items ?? [];
  } finally {
    loading.value = false;
  }
}

async function loadShares() {
  loading.value = true;
  try {
    const r = await adminListSharesApi(1, 100) as { data: { items: Record<string, unknown>[] } };
    shares.value = r.data?.items ?? [];
  } finally {
    loading.value = false;
  }
}

async function revokeShare(token: string) {
  await adminRevokeShareApi(token);
  await loadShares();
}

function openQuotaModal(q: QuotaRow) {
  quotaTarget.value = q;
  quotaInputGb.value = Math.round(q.quotaBytes / 1024 ** 3) || 10;
  quotaModal.value = true;
}

async function saveQuota() {
  if (!quotaTarget.value) return;
  quotaSaving.value = true;
  try {
    await adminUpdateQuotaApi(quotaTarget.value.tenantId, quotaInputGb.value * 1024 ** 3);
    quotaModal.value = false;
    await loadQuotas();
  } finally {
    quotaSaving.value = false;
  }
}

function fmtBytes(bytes: number): string {
  if (!bytes) return '0 B';
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

onMounted(async () => {
  await loadStats();
  await loadQuotas();
});
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- 顶部统计卡片 -->
    <div class="flex gap-4 p-4 border-b border-border shrink-0">
      <a-card size="small" class="flex-1 text-center">
        <a-statistic :title="$t('plugin.netdisk.admin.totalFiles')" :value="stats.total_files ?? 0" />
      </a-card>
      <a-card size="small" class="flex-1 text-center">
        <a-statistic :title="$t('plugin.netdisk.admin.totalUsed')" :value="fmtBytes(stats.total_used_bytes ?? 0)" />
      </a-card>
      <a-card size="small" class="flex-1 text-center">
        <a-statistic :title="$t('plugin.netdisk.admin.totalQuota')" :value="fmtBytes(stats.total_quota_bytes ?? 0)" />
      </a-card>
      <a-card size="small" class="flex-1 text-center">
        <a-statistic :title="$t('plugin.netdisk.admin.totalShares')" :value="stats.total_shares ?? 0" />
      </a-card>
    </div>

    <!-- Tab + 刷新 -->
    <div class="flex-1 flex flex-col overflow-hidden p-4">
      <a-tabs
        v-model:active-key="activeTab"
        size="small"
        @change="(k: string) => { if (k === 'quotas') loadQuotas(); else loadShares(); }"
      >
        <!-- 配额列表 -->
        <a-tab-pane key="quotas" :tab="$t('plugin.netdisk.admin.quotas')">
          <div class="mb-2 text-right">
            <a-button size="small" @click="loadQuotas">{{ $t('plugin.netdisk.action.refresh') }}</a-button>
          </div>
          <a-spin :spinning="loading">
            <a-table
              :data-source="quotas"
              :pagination="{ pageSize: 20 }"
              row-key="tenantId"
              size="small"
            >
              <a-table-column title="Tenant ID" data-index="tenantId" key="tenantId" :width="100">
                <template #default="{ record }"><code>#{{ record.tenantId }}</code></template>
              </a-table-column>
              <a-table-column :title="$t('plugin.netdisk.admin.totalQuota')" key="quota" :width="120">
                <template #default="{ record }">{{ fmtBytes(record.quotaBytes) }}</template>
              </a-table-column>
              <a-table-column :title="$t('plugin.netdisk.admin.totalUsed')" key="used" :width="120">
                <template #default="{ record }">{{ fmtBytes(record.usedBytes) }}</template>
              </a-table-column>
              <a-table-column title="%" key="percent" :width="180">
                <template #default="{ record }">
                  <a-progress
                    :percent="Number(record.usedPercent.toFixed(1))"
                    size="small"
                    :status="record.usedPercent >= 90 ? 'exception' : record.usedPercent >= 70 ? 'active' : 'normal'"
                  />
                </template>
              </a-table-column>
              <a-table-column :title="$t('plugin.netdisk.admin.actionCol')" key="actions" :width="160">
                <template #default="{ record }">
                  <a-space size="small">
                    <a-button size="small" @click="openQuotaModal(record)">
                      {{ $t('plugin.netdisk.admin.updateQuota') }}
                    </a-button>
                  </a-space>
                </template>
              </a-table-column>
            </a-table>
          </a-spin>
        </a-tab-pane>

        <!-- 分享审计 -->
        <a-tab-pane key="shares" :tab="$t('plugin.netdisk.admin.shares')">
          <div class="mb-2 text-right">
            <a-button size="small" @click="loadShares">{{ $t('plugin.netdisk.action.refresh') }}</a-button>
          </div>
          <a-spin :spinning="loading">
            <a-table
              :data-source="shares"
              :pagination="{ pageSize: 20 }"
              row-key="id"
              size="small"
            >
              <a-table-column title="Token" key="token" :width="140">
                <template #default="{ record }">
                  <code class="text-[11px]">{{ String(record.shareToken).slice(0, 12) }}...</code>
                </template>
              </a-table-column>
              <a-table-column :title="$t('plugin.netdisk.admin.tenantCol')" key="tenant" :width="90">
                <template #default="{ record }"><code>#{{ record.tenantId }}</code></template>
              </a-table-column>
              <a-table-column :title="$t('plugin.netdisk.admin.permCol')" data-index="permission" key="permission" :width="100" />
              <a-table-column :title="$t('plugin.netdisk.admin.accessCol')" data-index="accessCount" key="accessCount" :width="80" />
              <a-table-column :title="$t('plugin.netdisk.admin.statusCol')" key="status" :width="90">
                <template #default="{ record }">
                  <a-tag :color="record.isActive ? 'success' : 'error'">
                    {{ record.isActive ? $t('plugin.netdisk.admin.statusActive') : $t('plugin.netdisk.admin.statusRevoked') }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column :title="$t('plugin.netdisk.admin.actionCol')" key="actions" :width="120">
                <template #default="{ record }">
                  <a-button
                    v-if="record.isActive"
                    size="small"
                    danger
                    @click="revokeShare(String(record.shareToken))"
                  >
                    {{ $t('plugin.netdisk.admin.revokeShare') }}
                  </a-button>
                </template>
              </a-table-column>
            </a-table>
          </a-spin>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 配额更新弹窗 -->
    <a-modal
      v-model:open="quotaModal"
      :title="$t('plugin.netdisk.admin.updateQuota')"
      :confirm-loading="quotaSaving"
      @ok="saveQuota"
      @cancel="quotaModal = false"
    >
      <div v-if="quotaTarget" class="flex flex-col gap-3">
        <div>
          <span class="text-muted-foreground text-[13px]">
            Tenant #{{ quotaTarget.tenantId }} — {{ $t('plugin.netdisk.admin.totalUsed') }}:
            {{ fmtBytes(quotaTarget.usedBytes) }} / {{ fmtBytes(quotaTarget.quotaBytes) }}
          </span>
        </div>
        <a-form-item :label="$t('plugin.netdisk.admin.totalQuota') + ' (GB)'">
          <a-input-number
            v-model:value="quotaInputGb"
            :min="1"
            :max="10240"
            :step="1"
            class="w-40"
          />
        </a-form-item>
      </div>
    </a-modal>
  </div>
</template>
