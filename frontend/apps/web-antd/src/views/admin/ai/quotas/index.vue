<script lang="ts" setup>
import type {
  AIQuotaDiagnosticInfo,
  AIQuotaDiagnosticsSummaryInfo,
  AIRateLimitDiagnosticInfo,
  AIRateLimitInfo,
} from '#/api/admin/ai';

import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Card,
  Empty,
  Pagination,
  Progress,
  Select,
  Spin,
  Statistic,
  TabPane,
  Tabs,
  Tag,
} from 'ant-design-vue';

import {
  deleteAIQuotaApi,
  deleteAIRateLimitApi,
  getAIModelSelectApi,
  getAIQuotaListApi,
  getAIQuotaSummaryApi,
  getAIRateLimitListApi,
} from '#/api/admin/ai';
import { getTenantSelectApi } from '#/api/admin/tenant';
import {
  buildPageAIFormExtraData,
  createOpenPageOperation,
  createPrefilledCreatePageOperation,
  createRecordActionPageOperation,
  useCrudList,
  usePageAIOperations,
} from '#/composables';
import { $t } from '#/locales';
import { formatTokens } from '#/utils/format';

import {
  formatPercent,
  getActiveStateOptions,
  getFormDefaults,
  getPeriodOptions,
  getPeriodText,
  getQuotaTypeOptions,
  getQuotaTypeText,
  getRateLimitFormDefaults,
  getRuntimeStatusColor,
  getRuntimeStatusText,
  getScopeTypeText,
  getSourceColor,
  getSourceText,
  useQuotaPageAiFormSchema,
} from './data';
import Form from './modules/form.vue';
import RateLimitForm from './modules/RateLimitForm.vue';

defineOptions({ name: 'AIQuotaDiagnosticsPage' });

interface SelectOption {
  label: string;
  value: number;
}

interface SharedFilters {
  is_active?: 'false' | 'true';
  model_id?: number;
  tenant_id?: number;
}

interface RateLimitFormExposed {
  openEdit: (row: AIRateLimitInfo, extraData?: Record<string, unknown>) => void;
  openNew: (extraData?: Record<string, unknown>) => void;
}

interface RateLimitCreateOperationParams extends Record<string, unknown> {
  description?: string;
  is_active?: boolean;
  model_id?: number;
  rpm_limit?: number;
  tenant_id?: number;
  tpm_limit?: number;
}

interface RateLimitRecordOperationParams extends Record<string, unknown> {
  id: number;
}

const AI_PAGE_KEY = 'admin.ai.quotas';
const RATE_LIMIT_RESOURCE = '/admin/ai/quotas/rate-limits';

const activeTab = ref<'quotas' | 'rateLimits'>('quotas');
const tenantOptions = ref<SelectOption[]>([]);
const modelOptions = ref<SelectOption[]>([]);
const rateLimitFormRef = ref<RateLimitFormExposed>();

const summary = ref<AIQuotaDiagnosticsSummaryInfo>({
  active_quota_rules: 0,
  active_rate_limit_rules: 0,
  hard_quota_rules: 0,
  quota_exceeded_rules: 0,
  quota_warning_rules: 0,
  rate_limit_exceeded_rules: 0,
  rate_limit_warning_rules: 0,
  soft_quota_rules: 0,
  total_quota_rules: 0,
  total_rate_limit_rules: 0,
});
const summaryLoading = ref(false);

const sharedFilters = ref<SharedFilters>({});
const quotaPeriod = ref<string>();
const quotaType = ref<string>();

const summaryCards = computed(() => [
  {
    key: 'activeQuotaRules',
    label: $t('admin.ai.quota.summary.activeRules'),
    value: summary.value.active_quota_rules,
    icon: 'lucide:database',
    tone: 'text-primary',
    toneBg: 'bg-primary/10',
  },
  {
    key: 'hardQuotaRules',
    label: $t('admin.ai.quota.summary.blockRules'),
    value: summary.value.hard_quota_rules,
    icon: 'lucide:shield-alert',
    tone: 'text-destructive',
    toneBg: 'bg-destructive/10',
  },
  {
    key: 'quotaRisks',
    label: $t('admin.ai.quota.summary.riskRules'),
    value:
      summary.value.quota_warning_rules + summary.value.quota_exceeded_rules,
    icon: 'lucide:triangle-alert',
    tone: 'text-warning',
    toneBg: 'bg-warning/10',
  },
  {
    key: 'activeRateLimits',
    label: $t('admin.ai.quota.summary.rateLimitRules'),
    value: summary.value.active_rate_limit_rules,
    icon: 'lucide:gauge',
    tone: 'text-success',
    toneBg: 'bg-success/10',
  },
]);

async function loadSummary() {
  summaryLoading.value = true;
  try {
    summary.value = await getAIQuotaSummaryApi();
  } catch {
    // request interceptor handles errors / 请求拦截器统一处理错误
  } finally {
    summaryLoading.value = false;
  }
}

async function loadSelectOptions() {
  try {
    const [tenantResult, modelResult] = await Promise.all([
      getTenantSelectApi({ is_active: 'true' }),
      getAIModelSelectApi({ is_active: 'true' }),
    ]);
    tenantOptions.value = (tenantResult.items as SelectOption[]) || [];
    modelOptions.value = (modelResult.items as SelectOption[]) || [];
  } catch {
    tenantOptions.value = [];
    modelOptions.value = [];
  }
}

function buildSharedSearchParams() {
  return {
    ...(sharedFilters.value.tenant_id
      ? { 'filter[tenant_id][eq]': sharedFilters.value.tenant_id }
      : {}),
    ...(sharedFilters.value.model_id
      ? { 'filter[model_id][eq]': sharedFilters.value.model_id }
      : {}),
    ...(sharedFilters.value.is_active === undefined
      ? {}
      : { 'filter[is_active][eq]': sharedFilters.value.is_active }),
  };
}

function buildQuotaSearchParams() {
  return {
    ...buildSharedSearchParams(),
    ...(quotaPeriod.value ? { 'filter[period][eq]': quotaPeriod.value } : {}),
    ...(quotaType.value ? { 'filter[quota_type][eq]': quotaType.value } : {}),
  };
}

function buildRateLimitSearchParams() {
  return {
    ...buildSharedSearchParams(),
  };
}

function handleTenantFilterChange(value: unknown) {
  sharedFilters.value.tenant_id = typeof value === 'number' ? value : undefined;
  applyFilters();
}

function handleModelFilterChange(value: unknown) {
  sharedFilters.value.model_id = typeof value === 'number' ? value : undefined;
  applyFilters();
}

function handleActiveFilterChange(value: unknown) {
  sharedFilters.value.is_active =
    value === 'true' || value === 'false' ? value : undefined;
  applyFilters();
}

function handleQuotaPeriodChange(value: unknown) {
  quotaPeriod.value = typeof value === 'string' ? value : undefined;
  applyFilters();
}

function handleQuotaTypeChange(value: unknown) {
  quotaType.value = typeof value === 'string' ? value : undefined;
  applyFilters();
}

function normalizeRateLimitCreateParams(
  params: RateLimitCreateOperationParams,
): RateLimitCreateOperationParams {
  return {
    ...(typeof params?.tenant_id === 'number'
      ? { tenant_id: params.tenant_id }
      : {}),
    ...(typeof params?.model_id === 'number'
      ? { model_id: params.model_id }
      : {}),
    ...(typeof params?.rpm_limit === 'number'
      ? { rpm_limit: params.rpm_limit }
      : {}),
    ...(typeof params?.tpm_limit === 'number'
      ? { tpm_limit: params.tpm_limit }
      : {}),
    ...(typeof params?.description === 'string' && params.description.trim()
      ? { description: params.description.trim() }
      : {}),
    ...(typeof params?.is_active === 'boolean'
      ? { is_active: params.is_active }
      : {}),
  };
}

function buildRateLimitFormAiData(options?: {
  defaults?: Record<string, unknown>;
  overrides?: Record<string, unknown>;
}) {
  return buildPageAIFormExtraData({
    pageKey: AI_PAGE_KEY,
    resource: RATE_LIMIT_RESOURCE,
    ...(options?.defaults ? { defaults: options.defaults } : {}),
    ...(options?.overrides ? { overrides: options.overrides } : {}),
  });
}

function openRateLimitTab() {
  activeTab.value = 'rateLimits';
}

function openRateLimitCreate(extraData?: Record<string, unknown>) {
  openRateLimitTab();
  rateLimitFormRef.value?.openNew(extraData);
}

function openRateLimitEdit(
  row: AIRateLimitInfo,
  extraData?: Record<string, unknown>,
) {
  openRateLimitTab();
  rateLimitFormRef.value?.openEdit(row, extraData);
}

function resolveRateLimitRecord(
  params: Partial<RateLimitRecordOperationParams>,
): AIRateLimitInfo | undefined {
  const id = Number(params.id ?? 0);
  if (!Number.isFinite(id) || id <= 0) {
    return undefined;
  }
  return rateLimits.value.find((item) => item.id === id) as
    | AIRateLimitInfo
    | undefined;
}

const {
  list: quotas,
  total: quotaTotal,
  loading: quotaLoading,
  currentPage: quotaPage,
  pageSize: quotaPageSize,
  FormDrawer: QuotaFormDrawer,
  loadList: loadQuotas,
  onCreate: openQuotaCreate,
  onDelete: deleteQuota,
  onEdit: editQuota,
  onPageChange: onQuotaPageChange,
  onSearch: onQuotaSearch,
} = useCrudList<AIQuotaDiagnosticInfo>({
  api: {
    list: getAIQuotaListApi,
    delete: deleteAIQuotaApi,
    resource: '/admin/ai/quotas',
  },
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.ai.quota',
  nameField: 'id',
  pageSize: 9,
  createPermission: 'ai_quota:create',
  ai: {
    pageKey: AI_PAGE_KEY,
    formSchema: useQuotaPageAiFormSchema,
    entityName: $t('admin.ai.quota.name'),
    entityDescription: $t('admin.ai.quota.entityDescription'),
    contextExtras: () => ({
      active_tab: activeTab.value,
      active_quota_rules: summary.value.active_quota_rules,
      active_rate_limit_rules: summary.value.active_rate_limit_rules,
      hard_quota_rules: summary.value.hard_quota_rules,
      total_quota_rules: summary.value.total_quota_rules,
      total_rate_limit_rules: summary.value.total_rate_limit_rules,
    }),
    extra: [
      {
        name: 'refresh_list',
        label: $t('shared.pageOperation.refreshList'),
        description: $t('admin.ai.quota.aiOps.refreshDescription'),
        readonly: true,
        handler: async () => {
          await refreshAll();
          return {
            message: $t('shared.pageOperation.msg.listRefreshed'),
            success: true,
          };
        },
      },
      {
        name: 'create_record',
        label: $t('shared.pageOperation.createRecord'),
        description: $t('admin.ai.quota.aiOps.openCreateDescription'),
        readonly: false,
        handler: async () => {
          openQuotaCreate();
          return {
            message: $t('shared.pageOperation.msg.createFormOpenedEmpty'),
            success: true,
          };
        },
      },
    ],
  },
});

const {
  list: rateLimits,
  total: rateLimitTotal,
  loading: rateLimitLoading,
  currentPage: rateLimitPage,
  pageSize: rateLimitPageSize,
  loadList: loadRateLimits,
  onDelete: deleteRateLimit,
  onPageChange: onRateLimitPageChange,
  onSearch: onRateLimitSearch,
} = useCrudList<AIRateLimitDiagnosticInfo>({
  api: {
    list: getAIRateLimitListApi,
    delete: deleteAIRateLimitApi,
    resource: '/admin/ai/quotas/rate-limits',
  },
  formDefaults: getRateLimitFormDefaults,
  i18nPrefix: 'admin.ai.rateLimit',
  nameField: 'id',
  pageSize: 9,
  createPermission: 'ai_quota:create_rate_limit',
  customActions: {
    edit: (row) =>
      openRateLimitEdit(row as AIRateLimitInfo, {
        _aiPageKey: AI_PAGE_KEY,
      }),
  },
});

function applyFilters() {
  onQuotaSearch(buildQuotaSearchParams());
  onRateLimitSearch(buildRateLimitSearchParams());
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadQuotas(), loadRateLimits()]);
}

async function handleQuotaDelete(item: AIQuotaDiagnosticInfo) {
  await deleteQuota(item);
  await loadSummary();
}

async function handleRateLimitDelete(item: AIRateLimitDiagnosticInfo) {
  await deleteRateLimit(item);
  await loadSummary();
}

async function handleQuotaMutationSuccess() {
  await Promise.all([loadSummary(), loadQuotas()]);
}

async function handleRateLimitMutationSuccess() {
  await Promise.all([loadSummary(), loadRateLimits()]);
}

function progressStatus(isExceeded: boolean, isWarning: boolean) {
  if (isExceeded) return 'exception';
  if (isWarning) return 'active';
  return 'success';
}

usePageAIOperations({
  pageKey: AI_PAGE_KEY,
  operationStrategy: 'append',
  operations: [
    createOpenPageOperation({
      name: 'open_rate_limit_tab',
      label: $t('admin.ai.rateLimit.title'),
      description: $t('admin.ai.rateLimit.aiOps.openTabDescription'),
      open: async () => {
        openRateLimitTab();
      },
    }),
    createPrefilledCreatePageOperation<RateLimitCreateOperationParams>({
      name: 'create_rate_limit_rule',
      label: $t('admin.ai.rateLimit.create'),
      description: $t('admin.ai.rateLimit.aiOps.openCreateDescription'),
      params: {
        tenant_id: {
          type: 'number',
          description: $t('admin.ai.rateLimit.tenantId'),
        },
        model_id: {
          type: 'number',
          description: $t('admin.ai.rateLimit.modelId'),
        },
        rpm_limit: {
          type: 'number',
          description: $t('admin.ai.rateLimit.rpmLimit'),
        },
        tpm_limit: {
          type: 'number',
          description: $t('admin.ai.rateLimit.tpmLimit'),
        },
        description: {
          type: 'string',
          description: $t('admin.ai.rateLimit.description'),
        },
        is_active: {
          type: 'boolean',
          description: $t('admin.ai.rateLimit.isActive'),
        },
      },
      normalizeParams: normalizeRateLimitCreateParams,
      openCreate: async (defaults) => {
        openRateLimitCreate(buildRateLimitFormAiData({ defaults }));
      },
    }),
    createRecordActionPageOperation<
      AIRateLimitInfo,
      RateLimitRecordOperationParams
    >({
      name: 'edit_rate_limit_rule',
      label: $t('common.edit'),
      description: $t('admin.ai.rateLimit.aiOps.openEditDescription'),
      params: {
        id: {
          type: 'number',
          description: $t('admin.ai.rateLimit.aiOps.ruleId'),
          required: true,
        },
      },
      resolveRecord: resolveRateLimitRecord,
      resolveRecordId: (params) => params.id,
      action: async (record) => {
        openRateLimitEdit(record, {
          _aiPageKey: AI_PAGE_KEY,
        });
      },
    }),
    createRecordActionPageOperation<
      AIRateLimitInfo,
      RateLimitRecordOperationParams
    >({
      name: 'delete_rate_limit_rule',
      label: $t('common.delete'),
      description: $t('admin.ai.rateLimit.aiOps.deleteDescription'),
      params: {
        id: {
          type: 'number',
          description: $t('admin.ai.rateLimit.aiOps.ruleId'),
          required: true,
        },
      },
      resolveRecord: resolveRateLimitRecord,
      resolveRecordId: (params) => params.id,
      action: async (record) => {
        await handleRateLimitDelete(record as AIRateLimitDiagnosticInfo);
      },
    }),
  ],
});

onMounted(async () => {
  await Promise.all([loadSummary(), loadSelectOptions()]);
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.quota.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <QuotaFormDrawer @success="handleQuotaMutationSuccess" />
    <RateLimitForm
      ref="rateLimitFormRef"
      @success="handleRateLimitMutationSuccess"
    />

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card
        v-for="card in summaryCards"
        :key="card.key"
        :body-style="{ padding: '18px' }"
      >
        <Spin :spinning="summaryLoading">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <div class="text-sm text-muted-foreground">
                {{ card.label }}
              </div>
              <Statistic :value="card.value" class="mt-2" />
            </div>
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-2xl"
              :class="card.toneBg"
            >
              <IconifyIcon
                :icon="card.icon"
                class="size-5"
                :class="card.tone"
              />
            </div>
          </div>
        </Spin>
      </Card>
    </div>

    <div class="grid grid-cols-1 gap-3 xl:grid-cols-3">
      <Alert
        :message="$t('admin.ai.quota.helper.hardLimit')"
        show-icon
        type="error"
      />
      <Alert
        :message="$t('admin.ai.quota.helper.softLimit')"
        show-icon
        type="warning"
      />
      <Alert
        :message="$t('admin.ai.quota.helper.globalFallback')"
        show-icon
        type="info"
      />
    </div>

    <Card :body-style="{ padding: '20px' }">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <Select
            allow-clear
            class="w-44"
            :options="tenantOptions"
            :placeholder="$t('admin.ai.quota.placeholder.allTenants')"
            :value="sharedFilters.tenant_id"
            @change="handleTenantFilterChange"
          />
          <Select
            allow-clear
            class="w-44"
            :options="modelOptions"
            :placeholder="$t('admin.ai.usage.placeholder.selectModel')"
            :value="sharedFilters.model_id"
            @change="handleModelFilterChange"
          />
          <Select
            allow-clear
            class="w-36"
            :options="getActiveStateOptions()"
            :placeholder="$t('admin.ai.quota.placeholder.allStatus')"
            :value="sharedFilters.is_active"
            @change="handleActiveFilterChange"
          />
          <template v-if="activeTab === 'quotas'">
            <Select
              allow-clear
              class="w-36"
              :options="getPeriodOptions()"
              :placeholder="$t('admin.ai.quota.placeholder.allPeriods')"
              :value="quotaPeriod"
              @change="handleQuotaPeriodChange"
            />
            <Select
              allow-clear
              class="w-36"
              :options="getQuotaTypeOptions()"
              :placeholder="$t('admin.ai.quota.placeholder.allTypes')"
              :value="quotaType"
              @change="handleQuotaTypeChange"
            />
          </template>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <Button @click="refreshAll">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ $t('admin.ai.quota.refresh') }}
          </Button>
          <Button
            v-if="activeTab === 'quotas'"
            v-access:code="['ai_quota:create']"
            type="primary"
            @click="openQuotaCreate"
          >
            {{ $t('admin.ai.quota.create') }}
          </Button>
          <Button
            v-else
            v-access:code="['ai_quota:create_rate_limit']"
            type="primary"
            @click="openRateLimitCreate({ _aiPageKey: AI_PAGE_KEY })"
          >
            {{ $t('admin.ai.rateLimit.create') }}
          </Button>
        </div>
      </div>

      <Tabs v-model:active-key="activeTab">
        <TabPane key="quotas" :tab="$t('admin.ai.quota.title')">
          <Spin :spinning="quotaLoading">
            <div
              v-if="quotas.length > 0"
              class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in quotas"
                :key="item.id"
                class="overflow-hidden border-border/60"
                :body-style="{ padding: '18px' }"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <div
                        class="flex size-10 items-center justify-center rounded-2xl bg-primary/10"
                      >
                        <IconifyIcon
                          icon="lucide:shield"
                          class="size-5 text-primary"
                        />
                      </div>
                      <div class="min-w-0">
                        <div
                          class="truncate text-base font-semibold text-foreground"
                        >
                          {{ item.tenant_name || `Tenant #${item.tenant_id}` }}
                        </div>
                        <div class="mt-1 flex flex-wrap items-center gap-1.5">
                          <Tag color="blue" class="!mr-0">
                            {{
                              item.model_name ||
                              $t('admin.ai.quota.globalQuota')
                            }}
                          </Tag>
                          <Tag
                            :color="getRuntimeStatusColor(item.runtime_status)"
                            class="!mr-0"
                          >
                            {{ getRuntimeStatusText(item.runtime_status) }}
                          </Tag>
                          <Tag
                            :color="
                              item.is_latest_scope_rule ? 'success' : 'warning'
                            "
                            class="!mr-0"
                          >
                            {{
                              item.is_latest_scope_rule
                                ? $t('admin.ai.quota.latestRule')
                                : $t('admin.ai.quota.shadowedRule')
                            }}
                          </Tag>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="flex items-center gap-1">
                    <Button
                      v-access:code="['ai_quota:update']"
                      size="small"
                      type="text"
                      @click="editQuota(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:pencil" class="size-4" />
                      </template>
                    </Button>
                    <Button
                      v-access:code="['ai_quota:delete']"
                      danger
                      size="small"
                      type="text"
                      @click="handleQuotaDelete(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:trash-2" class="size-4" />
                      </template>
                    </Button>
                  </div>
                </div>

                <div class="mt-4 flex flex-wrap items-center gap-2">
                  <Tag color="default" class="!mr-0">
                    {{ $t('admin.ai.quota.scope') }}:
                    {{ getScopeTypeText(item.scope_type) }}
                  </Tag>
                  <Tag
                    :color="item.period === 'daily' ? 'orange' : 'geekblue'"
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
                </div>

                <div class="mt-4 rounded-2xl bg-accent/10 p-4">
                  <div class="mb-2 flex items-center justify-between text-sm">
                    <span class="text-muted-foreground">
                      {{ $t('admin.ai.quota.usage') }}
                    </span>
                    <span class="font-medium">
                      {{ formatTokens(item.usage) }} /
                      {{ formatTokens(item.limit) }}
                    </span>
                  </div>
                  <Progress
                    :percent="Math.min(item.usage_percent, 100)"
                    :show-info="false"
                    :status="progressStatus(item.is_exceeded, item.is_warning)"
                  />
                  <div
                    class="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm"
                  >
                    <span class="text-muted-foreground">
                      {{ $t('admin.ai.quota.remaining') }}:
                      <span class="font-medium text-foreground">
                        {{ formatTokens(item.remaining) }}
                      </span>
                    </span>
                    <span class="text-muted-foreground">
                      {{ formatPercent(item.usage_percent) }}
                    </span>
                  </div>
                  <div
                    class="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                  >
                    <span>
                      {{ $t('admin.ai.quota.warningThreshold') }}:
                      {{ item.warning_threshold ?? 80 }}%
                    </span>
                    <span v-if="item.is_warning">
                      {{ $t('admin.ai.quota.warningReached') }}
                    </span>
                  </div>
                </div>

                <div class="mt-4 space-y-2 text-sm">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('admin.ai.quota.response')
                    }}</span>
                    <span class="font-medium text-foreground">
                      {{
                        item.exhaustion_action === 'deny'
                          ? `HTTP ${item.exhaustion_http_status} / ${item.exhaustion_error_code}`
                          : $t('admin.ai.quota.helper.softLimit')
                      }}
                    </span>
                  </div>
                  <div class="text-xs text-muted-foreground">
                    {{
                      item.exhaustion_action === 'deny'
                        ? item.exhaustion_message_preview
                        : $t('admin.ai.quota.helper.softLimit')
                    }}
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>

          <div v-if="quotaTotal > quotaPageSize" class="mt-4 flex justify-end">
            <Pagination
              :current="quotaPage"
              :page-size="quotaPageSize"
              :total="quotaTotal"
              show-quick-jumper
              size="small"
              @change="onQuotaPageChange"
            />
          </div>
        </TabPane>

        <TabPane key="rateLimits" :tab="$t('admin.ai.rateLimit.title')">
          <div class="mb-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Alert
              :message="$t('admin.ai.rateLimit.helper.deny')"
              show-icon
              type="error"
            />
            <Alert
              :message="$t('admin.ai.rateLimit.helper.inherit')"
              show-icon
              type="info"
            />
          </div>

          <Spin :spinning="rateLimitLoading">
            <div
              v-if="rateLimits.length > 0"
              class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
            >
              <Card
                v-for="item in rateLimits"
                :key="item.id"
                class="overflow-hidden border-border/60"
                :body-style="{ padding: '18px' }"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <div
                        class="flex size-10 items-center justify-center rounded-2xl bg-success/10"
                      >
                        <IconifyIcon
                          icon="lucide:timer"
                          class="size-5 text-success"
                        />
                      </div>
                      <div class="min-w-0">
                        <div
                          class="truncate text-base font-semibold text-foreground"
                        >
                          {{ item.model_name || `Model #${item.model_id}` }}
                        </div>
                        <div class="mt-1 flex flex-wrap items-center gap-1.5">
                          <Tag color="blue" class="!mr-0">
                            {{
                              item.tenant_name || `Tenant #${item.tenant_id}`
                            }}
                          </Tag>
                          <Tag
                            :color="getRuntimeStatusColor(item.runtime_status)"
                            class="!mr-0"
                          >
                            {{ getRuntimeStatusText(item.runtime_status) }}
                          </Tag>
                          <Tag
                            :color="
                              item.is_latest_model_rule ? 'success' : 'warning'
                            "
                            class="!mr-0"
                          >
                            {{
                              item.is_latest_model_rule
                                ? $t('admin.ai.rateLimit.latestRule')
                                : $t('admin.ai.rateLimit.shadowedRule')
                            }}
                          </Tag>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="flex items-center gap-1">
                    <Button
                      v-access:code="['ai_quota:update_rate_limit']"
                      size="small"
                      type="text"
                      @click="
                        openRateLimitEdit(item, { _aiPageKey: AI_PAGE_KEY })
                      "
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:pencil" class="size-4" />
                      </template>
                    </Button>
                    <Button
                      v-access:code="['ai_quota:delete_rate_limit']"
                      danger
                      size="small"
                      type="text"
                      @click="handleRateLimitDelete(item)"
                    >
                      <template #icon>
                        <IconifyIcon icon="lucide:trash-2" class="size-4" />
                      </template>
                    </Button>
                  </div>
                </div>

                <div class="mt-4 grid grid-cols-1 gap-3">
                  <div class="rounded-2xl bg-accent/10 p-4">
                    <div class="mb-2 flex items-center justify-between text-sm">
                      <span class="text-muted-foreground">
                        {{ $t('admin.ai.rateLimit.currentRpm') }}
                      </span>
                      <span class="font-medium">
                        {{
                          item.effective_rpm_limit == null
                            ? $t('admin.ai.rateLimit.noLimit')
                            : `${item.current_rpm} / ${item.effective_rpm_limit}`
                        }}
                      </span>
                    </div>
                    <Progress
                      :percent="Math.min(item.rpm_usage_percent, 100)"
                      :show-info="false"
                      :status="
                        progressStatus(item.is_exceeded, item.is_warning)
                      "
                    />
                  </div>

                  <div class="rounded-2xl bg-accent/10 p-4">
                    <div class="mb-2 flex items-center justify-between text-sm">
                      <span class="text-muted-foreground">
                        {{ $t('admin.ai.rateLimit.currentTpm') }}
                      </span>
                      <span class="font-medium">
                        {{
                          item.effective_tpm_limit == null
                            ? $t('admin.ai.rateLimit.noLimit')
                            : `${formatTokens(item.current_tpm)} / ${formatTokens(item.effective_tpm_limit)}`
                        }}
                      </span>
                    </div>
                    <Progress
                      :percent="Math.min(item.tpm_usage_percent, 100)"
                      :show-info="false"
                      :status="
                        progressStatus(item.is_exceeded, item.is_warning)
                      "
                    />
                  </div>
                </div>

                <div class="mt-4 grid grid-cols-1 gap-2 text-sm">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('admin.ai.rateLimit.configured')
                    }}</span>
                    <span class="font-medium text-foreground">
                      RPM {{ item.configured_rpm_limit ?? '-' }} / TPM
                      {{
                        item.configured_tpm_limit == null
                          ? '-'
                          : formatTokens(item.configured_tpm_limit)
                      }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('admin.ai.rateLimit.modelDefault')
                    }}</span>
                    <span class="font-medium text-foreground">
                      RPM {{ item.model_default_rpm_limit ?? '-' }} / TPM
                      {{
                        item.model_default_tpm_limit == null
                          ? '-'
                          : formatTokens(item.model_default_tpm_limit)
                      }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-muted-foreground">{{
                      $t('admin.ai.rateLimit.effective')
                    }}</span>
                    <span
                      class="flex flex-wrap items-center justify-end gap-1.5"
                    >
                      <Tag
                        :color="getSourceColor(item.rpm_source)"
                        class="!mr-0"
                      >
                        RPM {{ getSourceText(item.rpm_source) }}
                      </Tag>
                      <Tag
                        :color="getSourceColor(item.tpm_source)"
                        class="!mr-0"
                      >
                        TPM {{ getSourceText(item.tpm_source) }}
                      </Tag>
                    </span>
                  </div>
                </div>

                <div class="mt-4 text-xs text-muted-foreground">
                  {{ $t('admin.ai.rateLimit.response') }}: HTTP
                  {{ item.exhaustion_http_status }} /
                  {{ item.exhaustion_error_code }}
                  <div class="mt-1">
                    {{ item.exhaustion_message_preview }}
                  </div>
                </div>
              </Card>
            </div>
            <Empty v-else :description="$t('common.noData')" class="py-16" />
          </Spin>

          <div
            v-if="rateLimitTotal > rateLimitPageSize"
            class="mt-4 flex justify-end"
          >
            <Pagination
              :current="rateLimitPage"
              :page-size="rateLimitPageSize"
              :total="rateLimitTotal"
              show-quick-jumper
              size="small"
              @change="onRateLimitPageChange"
            />
          </div>
        </TabPane>
      </Tabs>
    </Card>
  </Page>
</template>
