<script lang="ts" setup>
/**
 * 租户端配额与速率限制管理页面
 */
import type {
  TenantQuotaWithUsageInfo,
  TenantRateLimitInfo,
} from '#/api/tenant/ai';

defineOptions({ name: 'TenantAIQuotas' });

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  message,
  Modal,
  Progress,
  Spin,
  Tabs,
  TabPane,
  Tag,
} from 'ant-design-vue';

import {
  deleteTenantQuotaApi,
  deleteTenantRateLimitApi,
  getTenantQuotasApi,
  getTenantRateLimitsApi,
} from '#/api/tenant/ai';
import { $t } from '#/locales';

import {
  formatTokens,
  getPeriodText,
  getQuotaTypeText,
} from './data';
import QuotaForm from './modules/QuotaForm.vue';
import RateLimitForm from './modules/RateLimitForm.vue';

// ============ 配额 ============

const quotaLoading = ref(false);
const quotas = ref<TenantQuotaWithUsageInfo[]>([]);
const quotaFormRef = ref<InstanceType<typeof QuotaForm>>();

async function loadQuotas() {
  quotaLoading.value = true;
  try {
    quotas.value = await getTenantQuotasApi();
  } catch {
    // Error handled by request interceptor
  } finally {
    quotaLoading.value = false;
  }
}

function handleCreateQuota() {
  quotaFormRef.value?.openNew();
}

function handleEditQuota(item: TenantQuotaWithUsageInfo) {
  quotaFormRef.value?.openEdit(item.quota);
}

function handleDeleteQuota(item: TenantQuotaWithUsageInfo) {
  Modal.confirm({
    title: $t('tenant.ai.quota.confirmDelete'),
    onOk: async () => {
      try {
        await deleteTenantQuotaApi(item.quota.id);
        message.success($t('tenant.ai.quota.messages.deleteSuccess'));
        await loadQuotas();
      } catch {
        // Error handled by request interceptor
      }
    },
  });
}

/**
 * 获取进度条颜色
 */
function getProgressColor(item: TenantQuotaWithUsageInfo): string {
  if (item.is_exceeded) return '#ff4d4f';
  if (item.is_warning) return '#faad14';
  return '#52c41a';
}

// ============ 速率限制 ============

const rateLimitLoading = ref(false);
const rateLimits = ref<TenantRateLimitInfo[]>([]);
const rateLimitFormRef = ref<InstanceType<typeof RateLimitForm>>();

async function loadRateLimits() {
  rateLimitLoading.value = true;
  try {
    rateLimits.value = await getTenantRateLimitsApi();
  } catch {
    // Error handled by request interceptor
  } finally {
    rateLimitLoading.value = false;
  }
}

function handleCreateRateLimit() {
  rateLimitFormRef.value?.openNew();
}

function handleEditRateLimit(item: TenantRateLimitInfo) {
  rateLimitFormRef.value?.openEdit(item);
}

function handleDeleteRateLimit(item: TenantRateLimitInfo) {
  Modal.confirm({
    title: $t('tenant.ai.rateLimit.confirmDelete'),
    onOk: async () => {
      try {
        await deleteTenantRateLimitApi(item.id);
        message.success($t('tenant.ai.rateLimit.messages.deleteSuccess'));
        await loadRateLimits();
      } catch {
        // Error handled by request interceptor
      }
    },
  });
}

function handleTabChange(key: number | string) {
  if (key === 'rateLimits' && rateLimits.value.length === 0) {
    loadRateLimits();
  }
}

onMounted(loadQuotas);
</script>

<template>
  <Page auto-content-height :description="$t('tenant.ai.quota.pageDesc')" content-class="flex flex-col gap-4">
    <!-- 表单抽屉 -->
    <QuotaForm ref="quotaFormRef" @success="loadQuotas" />
    <RateLimitForm ref="rateLimitFormRef" @success="loadRateLimits" />

    <Card :body-style="{ padding: '0' }">
      <Tabs default-active-key="quotas" class="px-4" @change="handleTabChange">
        <!-- ========== 配额 Tab ========== -->
        <TabPane key="quotas" :tab="$t('tenant.ai.quota.title')">
          <!-- 操作栏 -->
          <div class="mb-4 flex items-center justify-between">
            <span class="text-sm text-muted-foreground">
              {{ quotas.length }} {{ $t('tenant.ai.quota.title') }}
            </span>
            <Button
              v-access:code="['ai_quota:create_quota']"
              type="primary"
              @click="handleCreateQuota"
            >
              <template #icon><Plus class="size-4" /></template>
              {{ $t('tenant.ai.quota.create') }}
            </Button>
          </div>

          <!-- 配额列表 -->
          <Spin :spinning="quotaLoading">
            <div v-if="quotas.length > 0" class="flex flex-col gap-3 pb-4">
              <Card
                v-for="item in quotas"
                :key="item.quota.id"
                class="transition-shadow duration-200 hover:shadow-md"
                :body-style="{ padding: '16px' }"
              >
                <div class="flex items-start justify-between">
                  <!-- 左侧信息 -->
                  <div class="flex-1">
                    <div class="mb-2 flex items-center gap-2">
                      <div class="flex size-9 items-center justify-center rounded-lg bg-primary/10">
                        <IconifyIcon icon="lucide:gauge" class="size-4.5 text-primary" />
                      </div>
                      <div>
                        <div class="flex items-center gap-2">
                          <span v-if="item.quota.model_name" class="font-medium text-foreground">
                            {{ item.quota.model_name }}
                          </span>
                          <span v-else-if="item.quota.model_id" class="font-medium text-foreground">
                            {{ $t('tenant.ai.quota.modelId') }} #{{ item.quota.model_id }}
                          </span>
                          <Tag v-else color="blue">
                            {{ $t('tenant.ai.quota.globalQuota') }}
                          </Tag>
                          <Tag :color="item.quota.period === 'daily' ? 'orange' : 'blue'">
                            {{ getPeriodText(item.quota.period) }}
                          </Tag>
                          <Tag :color="item.quota.quota_type === 'hard' ? 'red' : 'green'">
                            {{ getQuotaTypeText(item.quota.quota_type) }}
                          </Tag>
                        </div>
                        <div v-if="item.quota.description" class="mt-0.5 text-xs text-muted-foreground">
                          {{ item.quota.description }}
                        </div>
                      </div>
                    </div>

                    <!-- 进度条 -->
                    <div class="mt-3">
                      <div class="mb-1 flex items-center justify-between text-sm">
                        <span class="text-muted-foreground">
                          {{ $t('tenant.ai.quota.usage') }}:
                          <span class="font-mono font-medium text-foreground">
                            {{ formatTokens(item.usage) }}
                          </span>
                          / {{ formatTokens(item.limit) }}
                        </span>
                        <span
                          class="font-medium"
                          :class="{
                            'text-destructive': item.is_exceeded,
                            'text-warning': item.is_warning && !item.is_exceeded,
                            'text-success': !item.is_warning,
                          }"
                        >
                          {{ item.usage_percent.toFixed(1) }}%
                        </span>
                      </div>
                      <Progress
                        :percent="Math.min(item.usage_percent, 100)"
                        :show-info="false"
                        :stroke-color="getProgressColor(item)"
                        size="small"
                      />
                      <div class="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                        <span>
                          {{ $t('tenant.ai.quota.remaining') }}: {{ formatTokens(item.remaining) }}
                        </span>
                        <Tag v-if="item.is_exceeded" color="error" class="text-xs">
                          {{ $t('tenant.ai.quota.exceeded') }}
                        </Tag>
                        <Tag v-else-if="item.is_warning" color="warning" class="text-xs">
                          {{ $t('tenant.ai.quota.warning') }}
                        </Tag>
                      </div>
                    </div>
                  </div>

                  <!-- 右侧操作 -->
                  <div class="ml-4 flex items-center gap-1">
                    <Button
                      v-access:code="['ai_quota:update_quota']"
                      type="text"
                      size="small"
                      @click="handleEditQuota(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:pencil" class="size-4" />
                      </template>
                    </Button>
                    <Button
                      v-access:code="['ai_quota:delete_quota']"
                      type="text"
                      danger
                      size="small"
                      @click="handleDeleteQuota(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:trash-2" class="size-4" />
                      </template>
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>
        </TabPane>

        <!-- ========== 速率限制 Tab ========== -->
        <TabPane key="rateLimits" :tab="$t('tenant.ai.rateLimit.title')">
          <!-- 操作栏 -->
          <div class="mb-4 flex items-center justify-between">
            <span class="text-sm text-muted-foreground">
              {{ rateLimits.length }} {{ $t('tenant.ai.rateLimit.title') }}
            </span>
            <Button
              v-access:code="['ai_quota:create_rate_limit']"
              type="primary"
              @click="handleCreateRateLimit"
            >
              <template #icon><Plus class="size-4" /></template>
              {{ $t('tenant.ai.rateLimit.create') }}
            </Button>
          </div>

          <!-- 速率限制列表 -->
          <Spin :spinning="rateLimitLoading">
            <div v-if="rateLimits.length > 0" class="flex flex-col gap-3 pb-4">
              <Card
                v-for="item in rateLimits"
                :key="item.id"
                class="transition-shadow duration-200 hover:shadow-md"
                :body-style="{ padding: '16px' }"
              >
                <div class="flex items-center justify-between">
                  <!-- 左侧信息 -->
                  <div class="flex items-center gap-3">
                    <div
                      class="flex size-10 items-center justify-center rounded-lg"
                      :class="item.is_active ? 'bg-primary/10' : 'bg-muted'"
                    >
                      <IconifyIcon
                        icon="lucide:timer"
                        class="size-5"
                        :class="item.is_active ? 'text-primary' : 'text-muted-foreground'"
                      />
                    </div>
                    <div>
                      <div class="flex items-center gap-2">
                        <span class="font-medium text-foreground">
                          {{ item.model_name || `${$t('tenant.ai.rateLimit.modelId')} #${item.model_id}` }}
                        </span>
                        <Tag :color="item.is_active ? 'success' : 'default'">
                          {{
                            item.is_active
                              ? $t('tenant.ai.rateLimit.isActive')
                              : $t('common.disabled')
                          }}
                        </Tag>
                      </div>
                      <div class="mt-1 flex items-center gap-4 text-sm text-muted-foreground">
                        <span>
                          {{ $t('tenant.ai.rateLimit.rpmLimit') }}:
                          <span class="font-mono font-medium text-foreground">
                            {{ item.rpm_limit ?? $t('tenant.ai.rateLimit.noLimit') }}
                          </span>
                          <span v-if="item.rpm_limit" class="ml-0.5">{{ $t('tenant.ai.rateLimit.rpmUnit') }}</span>
                        </span>
                        <span>
                          {{ $t('tenant.ai.rateLimit.tpmLimit') }}:
                          <span class="font-mono font-medium text-foreground">
                            {{ item.tpm_limit ? formatTokens(item.tpm_limit) : $t('tenant.ai.rateLimit.noLimit') }}
                          </span>
                          <span v-if="item.tpm_limit" class="ml-0.5">{{ $t('tenant.ai.rateLimit.tpmUnit') }}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <!-- 右侧操作 -->
                  <div class="flex items-center gap-1">
                    <Button
                      v-access:code="['ai_quota:update_rate_limit']"
                      type="text"
                      size="small"
                      @click="handleEditRateLimit(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:pencil" class="size-4" />
                      </template>
                    </Button>
                    <Button
                      v-access:code="['ai_quota:delete_rate_limit']"
                      type="text"
                      danger
                      size="small"
                      @click="handleDeleteRateLimit(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:trash-2" class="size-4" />
                      </template>
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>
        </TabPane>
      </Tabs>
    </Card>
  </Page>
</template>
