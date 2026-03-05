<script lang="ts" setup>
/**
 * AI 配额与速率限制管理页面（管理端）— useCrudList 声明式卡片布局
 */
import type { AIQuotaInfo, AIRateLimitInfo } from '#/api/admin/ai';

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Card,
  Empty,
  Pagination,
  Select,
  Spin,
  TabPane,
  Tabs,
  Tag,
} from 'ant-design-vue';

import {
  deleteAIQuotaApi,
  deleteAIRateLimitApi,
  getAIQuotaListApi,
  getAIRateLimitListApi,
} from '#/api/admin/ai';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatTokens } from '#/utils/format';

import {
  getFormDefaults,
  getPeriodOptions,
  getPeriodText,
  getQuotaTypeOptions,
  getQuotaTypeText,
  getRateLimitFormDefaults,
} from './data';
import Form from './modules/form.vue';
import RateLimitForm from './modules/RateLimitForm.vue';

defineOptions({ name: 'AIQuotaList' });

interface RateLimitFormExposed {
  openNew: () => void;
  openEdit: (row: AIRateLimitInfo) => void;
}

// ========== 配额 Tab — useCrudList ==========
const {
  list: quotas,
  total: quotaTotal,
  loading: quotaLoading,
  currentPage: quotaPage,
  pageSize: quotaPageSize,
  FormDrawer: QuotaFormDrawer,
  loadList: loadQuotas,
  onCreate: onCreateQuota,
  handleMenuAction: handleQuotaAction,
  onPageChange: onQuotaPageChange,
  onSearch: onQuotaSearch,
} = useCrudList<AIQuotaInfo>({
  api: {
    list: getAIQuotaListApi,
    delete: deleteAIQuotaApi,
    resource: '/admin/ai/quotas',
  },
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.ai.quota',
  nameField: 'id',
  pageSize: 12,
  defaultSort: '-created_at',
  createPermission: 'ai_quota:create',
});

// ========== 速率限制 Tab — useCrudList + ref 模式 ==========
const rateLimitFormRef = ref<RateLimitFormExposed>();

const {
  list: rateLimits,
  loading: rateLimitLoading,
  loadList: loadRateLimits,
  handleMenuAction: handleRateLimitAction,
} = useCrudList<AIRateLimitInfo>({
  api: {
    list: getAIRateLimitListApi,
    delete: deleteAIRateLimitApi,
    resource: '/admin/ai/quotas/rate-limits',
  },
  formDefaults: getRateLimitFormDefaults,
  i18nPrefix: 'admin.ai.rateLimit',
  nameField: 'id',
  pager: false,
  responseAdapter: (data) => ({
    items: Array.isArray(data) ? data : [],
    total: Array.isArray(data) ? (data as unknown[]).length : 0,
  }),
  customActions: {
    edit: (row) => rateLimitFormRef.value?.openEdit(row as AIRateLimitInfo),
  },
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.quota.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <!-- 配额表单抽屉 -->
    <QuotaFormDrawer @success="loadQuotas" />
    <!-- 速率限制表单（ref 模式） -->
    <RateLimitForm ref="rateLimitFormRef" @success="loadRateLimits" />

    <Card :body-style="{ padding: '0' }">
      <Tabs default-active-key="quotas" class="px-4">
        <!-- ========== 配额 Tab ========== -->
        <TabPane key="quotas" :tab="$t('admin.ai.quota.title')">
          <!-- 操作栏：过滤 + 新建 -->
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div class="flex flex-wrap items-center gap-2">
              <Select
                allow-clear
                class="w-36"
                :placeholder="$t('admin.ai.quota.placeholder.allPeriods')"
                :options="getPeriodOptions()"
                @change="
                  (v) => onQuotaSearch({ 'filter[period][eq]': v ?? undefined })
                "
              />
              <Select
                allow-clear
                class="w-32"
                :placeholder="$t('admin.ai.quota.placeholder.allTypes')"
                :options="getQuotaTypeOptions()"
                @change="
                  (v) =>
                    onQuotaSearch({ 'filter[quota_type][eq]': v ?? undefined })
                "
              />
            </div>
            <Button
              v-access:code="['ai_quota:create']"
              type="primary"
              @click="onCreateQuota"
            >
              {{ $t('admin.ai.quota.create') }}
            </Button>
          </div>

          <!-- 卡片网格 -->
          <Spin :spinning="quotaLoading">
            <div
              v-if="quotas.length > 0"
              class="grid grid-cols-1 gap-3 pb-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in quotas"
                :key="item.id"
                class="transition-shadow duration-200 hover:shadow-md"
                :body-style="{ padding: '16px' }"
              >
                <div class="flex items-start justify-between gap-2">
                  <!-- 左侧信息 -->
                  <div class="flex min-w-0 flex-1 items-start gap-2.5">
                    <div
                      class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10"
                    >
                      <IconifyIcon
                        icon="lucide:gauge"
                        class="size-4.5 text-primary"
                      />
                    </div>
                    <div class="min-w-0">
                      <div class="flex flex-wrap items-center gap-1.5">
                        <span class="font-medium text-foreground">
                          {{
                            item.tenant_name || $t('admin.ai.quota.globalQuota')
                          }}
                        </span>
                        <Tag color="blue">
                          {{
                            item.model_name || $t('admin.ai.quota.globalQuota')
                          }}
                        </Tag>
                      </div>
                      <div
                        class="mt-1.5 flex flex-wrap items-center gap-1.5 text-sm"
                      >
                        <Tag
                          :color="item.period === 'daily' ? 'orange' : 'blue'"
                          class="!mr-0"
                        >
                          {{ getPeriodText(item.period) }}
                        </Tag>
                        <Tag
                          :color="item.quota_type === 'hard' ? 'red' : 'green'"
                          class="!mr-0"
                        >
                          {{ getQuotaTypeText(item.quota_type) }}
                        </Tag>
                        <span class="text-muted-foreground">
                          {{ $t('admin.ai.quota.limit') }}:
                          <span class="font-mono font-medium text-foreground">{{
                            formatTokens(item.limit)
                          }}</span>
                          <span class="ml-0.5 text-xs">tokens</span>
                        </span>
                        <span
                          v-if="item.warning_threshold != null"
                          class="text-xs text-muted-foreground"
                        >
                          {{ $t('admin.ai.quota.warningThreshold') }}:
                          {{ item.warning_threshold }}%
                        </span>
                      </div>
                    </div>
                  </div>
                  <!-- 右侧：状态 + 操作 -->
                  <div class="flex shrink-0 items-center gap-1">
                    <Tag
                      :color="item.is_active ? 'success' : 'default'"
                      class="!mr-0"
                    >
                      {{
                        item.is_active
                          ? $t('admin.common.enabled')
                          : $t('admin.common.disabled')
                      }}
                    </Tag>
                    <Button
                      v-access:code="['ai_quota:update']"
                      type="text"
                      size="small"
                      @click="handleQuotaAction('edit', item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                      </template>
                    </Button>
                    <Button
                      v-access:code="['ai_quota:delete']"
                      type="text"
                      size="small"
                      danger
                      @click="handleQuotaAction('delete', item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
                      </template>
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>

          <!-- 分页 -->
          <div v-if="quotaTotal > quotaPageSize" class="flex justify-end py-4">
            <Pagination
              :current="quotaPage"
              :total="quotaTotal"
              :page-size="quotaPageSize"
              size="small"
              show-quick-jumper
              @change="onQuotaPageChange"
            />
          </div>
        </TabPane>

        <!-- ========== 速率限制 Tab ========== -->
        <TabPane key="rateLimits" :tab="$t('admin.ai.rateLimit.title')">
          <!-- 操作栏 -->
          <div class="mb-4 flex items-center justify-between">
            <span class="text-sm text-muted-foreground">
              {{ rateLimits.length }} {{ $t('admin.ai.rateLimit.title') }}
            </span>
            <Button
              v-access:code="['ai_quota:create_rate_limit']"
              type="primary"
              @click="rateLimitFormRef?.openNew()"
            >
              {{ $t('admin.ai.rateLimit.create') }}
            </Button>
          </div>

          <!-- 卡片网格 -->
          <Spin :spinning="rateLimitLoading">
            <div
              v-if="rateLimits.length > 0"
              class="grid grid-cols-1 gap-3 pb-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in rateLimits"
                :key="item.id"
                class="transition-shadow duration-200 hover:shadow-md"
                :body-style="{ padding: '16px' }"
              >
                <div class="flex items-start justify-between gap-2">
                  <!-- 左侧信息 -->
                  <div class="flex items-center gap-2.5">
                    <div
                      class="flex size-9 shrink-0 items-center justify-center rounded-lg"
                      :class="item.is_active ? 'bg-primary/10' : 'bg-muted'"
                    >
                      <IconifyIcon
                        icon="lucide:timer"
                        class="size-4.5"
                        :class="
                          item.is_active
                            ? 'text-primary'
                            : 'text-muted-foreground'
                        "
                      />
                    </div>
                    <div>
                      <div class="flex flex-wrap items-center gap-1.5">
                        <span class="font-medium text-foreground">
                          {{ item.model_name || `Model #${item.model_id}` }}
                        </span>
                        <Tag color="blue" class="!mr-0">
                          {{ $t('admin.ai.rateLimit.tenantLabel') }}
                          {{ item.tenant_id }}
                        </Tag>
                      </div>
                      <div
                        class="mt-1 flex items-center gap-4 text-sm text-muted-foreground"
                      >
                        <span>
                          RPM:
                          <span class="font-mono font-medium text-foreground">
                            {{
                              item.rpm_limit ?? $t('admin.ai.rateLimit.noLimit')
                            }}
                          </span>
                        </span>
                        <span>
                          TPM:
                          <span class="font-mono font-medium text-foreground">
                            {{
                              item.tpm_limit
                                ? formatTokens(item.tpm_limit)
                                : $t('admin.ai.rateLimit.noLimit')
                            }}
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <!-- 右侧：状态 + 操作 -->
                  <div class="flex shrink-0 items-center gap-1">
                    <Tag
                      :color="item.is_active ? 'success' : 'default'"
                      class="!mr-0"
                    >
                      {{
                        item.is_active
                          ? $t('admin.common.enabled')
                          : $t('admin.common.disabled')
                      }}
                    </Tag>
                    <Button
                      v-access:code="['ai_quota:update_rate_limit']"
                      type="text"
                      size="small"
                      @click="handleRateLimitAction('edit', item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:pencil" class="size-3.5" />
                      </template>
                    </Button>
                    <Button
                      v-access:code="['ai_quota:delete_rate_limit']"
                      type="text"
                      size="small"
                      danger
                      @click="handleRateLimitAction('delete', item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:trash-2" class="size-3.5" />
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
