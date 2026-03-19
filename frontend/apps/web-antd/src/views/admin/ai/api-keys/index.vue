<script lang="ts" setup>
/**
 * AI API Key 管理列表页面
 * AI API Key management list page
 */
import type { AIApiKeyInfo } from '#/api/admin/ai';

import { onUnmounted } from 'vue';

import { registerPageContext } from '#/components/business/ai-slide-panel/page-context-registry';
import { registerPageOperations } from '#/components/business/ai-slide-panel/page-operation-registry';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { message, Modal, Progress, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAIApiKeyListApi, toggleAIApiKeyStatusApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { getProcessedImageUrl } from '#/utils/image';
import { getScopeColor, getScopeIcon, getScopeText } from '#/utils/scope-helpers';

import { getFormDefaults, useColumns, useFormSchema, useGridFormSchema } from './data';
import Form from './modules/form.vue';

defineOptions({ name: 'AIApiKeyList' });

async function onCopyKeyPreview(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    message.success($t('admin.ai.apiKey.messages.copied'));
  } catch {
    message.error($t('admin.ai.apiKey.messages.copyFailed'));
  }
}

function onToggleActive(row: AIApiKeyInfo) {
  const isDisabling = row.is_active;
  Modal.confirm({
    title: isDisabling
      ? $t('admin.ai.apiKey.messages.confirmDisable')
      : $t('admin.ai.apiKey.messages.confirmEnable'),
    onOk: async () => {
      try {
        await toggleAIApiKeyStatusApi(row.id);
        message.success($t('admin.ai.apiKey.messages.toggleSuccess'));
        onRefresh();
      } catch {
        // Error handled by request interceptor / 错误由请求拦截器处理
      }
    },
  });
}

const { Grid, FormDrawer, onRefresh, onCreate, gridApi, formAiOperations } = useCrudPage<AIApiKeyInfo>({
  api: {
    list: getAIApiKeyListApi,
    resource: '/admin/ai/api-keys',
  },
  columns: useColumns,
  searchSchema: useGridFormSchema(),
  formComponent: Form,
  formDefaults: getFormDefaults,
  i18nPrefix: 'admin.ai.apiKey',
  nameField: 'name',
  defaultSort: '-created_at',
  createPermission: 'ai_api_key:create',
  recycleBin: true,
  ai: {
    pageKey: 'admin.ai.api-keys',
    formSchema: (isEdit?: boolean) => useFormSchema(Boolean(isEdit)),
  },
});

const cleanupPageContext = registerPageContext('admin/ai/api-keys', () => ({
  page_key: 'admin.ai.api-keys',
  page_title: $t('admin.ai.apiKey.name'),
  page_data: {
    resource: '/admin/ai/api-keys',
  },
}));

const cleanupPageOps = registerPageOperations('admin.ai.api-keys', [
  {
    name: 'refresh_list',
    label: $t('shared.pageOperation.refreshList'),
    description: 'Reload the API key list',
    readonly: true,
    handler: async () => {
      onRefresh();
      return { success: true, message: 'API key list refreshed' };
    },
  },
  {
    name: 'create_record',
    label: $t('shared.pageOperation.createApiKey'),
    description: 'Open the create API key form',
    readonly: false,
    handler: async () => {
      onCreate();
      return { success: true, message: 'Create API key form opened' };
    },
  },
  {
    name: 'search',
    label: $t('shared.pageOperation.searchByKeyword'),
    description: 'Search API keys by keyword',
    readonly: true,
    params: {
      keyword: { type: 'string', description: 'Search keyword' },
    },
    handler: async (params) => {
      const keyword = (params?.keyword as string) || '';
      gridApi.formApi?.setValues({ 'filter[name][ilike]': keyword });
      gridApi.reload({ page: 1 });
      return { success: true, message: `Searched for: ${keyword}` };
    },
  },
  ...formAiOperations,
]);

onUnmounted(() => {
  cleanupPageContext();
  cleanupPageOps();
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.apiKey.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <FormDrawer @success="onRefresh" />

    <Grid>
      <!-- 名称列 / Name column -->
      <template #name_cell="{ row }">
        <div class="flex items-center gap-2">
          <div
            class="flex size-8 items-center justify-center rounded-lg"
            :class="row.is_available ? 'bg-success/10' : 'bg-muted'"
          >
            <IconifyIcon
              icon="lucide:key"
              class="size-4"
              :class="
                row.is_available ? 'text-success' : 'text-muted-foreground'
              "
            />
          </div>
          <div class="flex flex-col">
            <span class="font-medium text-foreground">{{ row.name }}</span>
            <Tooltip
              v-if="row.last_used_at"
              :title="formatDate(row.last_used_at)"
            >
              <span class="text-xs text-muted-foreground">
                {{ $t('admin.ai.apiKey.lastUsedAt') }}:
                {{ formatRelativeTime(row.last_used_at) }}
              </span>
            </Tooltip>
          </div>
        </div>
      </template>

      <!-- Key 预览列 / Key preview column -->
      <template #keyPreview_cell="{ row }">
        <div v-if="row.key_preview" class="flex items-center gap-1">
          <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
            {{ row.key_preview }}
          </code>
          <Tooltip :title="$t('admin.ai.apiKey.messages.copy')">
            <button
              class="flex size-5 items-center justify-center rounded text-muted-foreground transition-colors hover:text-primary"
              @click="onCopyKeyPreview(row.key_preview)"
            >
              <IconifyIcon icon="lucide:copy" class="size-3" />
            </button>
          </Tooltip>
        </div>
        <span v-else class="text-muted-foreground">-</span>
      </template>

      <!-- 供应商列：图标 + 名称 + 模型数 / Provider column: icon + name + model count -->
      <template #providerName_cell="{ row }">
        <div
          v-if="row.provider_name"
          class="flex flex-col items-center gap-0.5"
        >
          <div class="flex items-center gap-1.5">
            <img
              v-if="row.provider_icon && Number(row.provider_icon) > 0"
              :src="getProcessedImageUrl(Number(row.provider_icon), { preset: 'small' })"
              class="size-4 shrink-0 rounded object-contain"
              alt=""
            />
            <IconifyIcon
              v-else
              icon="lucide:cpu"
              class="size-3.5 text-muted-foreground"
            />
            <span class="text-foreground">{{ row.provider_name }}</span>
          </div>
          <span
            v-if="row.provider_model_count > 0"
            class="text-[11px] text-muted-foreground"
          >
            {{ $t('admin.ai.apiKey.providerModels', { count: row.provider_model_count }) }}
          </span>
        </div>
        <span v-else class="text-muted-foreground">-</span>
      </template>

      <!-- 作用域列 / Scope column -->
      <template #scope_cell="{ row }">
        <div class="flex flex-col items-center gap-0.5">
          <Tag
            :color="getScopeColor(row.scope)"
            class="!mr-0 !text-[11px]"
            style="padding: 0 6px; line-height: 20px"
          >
            <div class="flex items-center gap-1">
              <IconifyIcon :icon="getScopeIcon(row.scope)" class="size-3" />
              <span>{{ getScopeText(row.scope) }}</span>
            </div>
          </Tag>
          <span
            v-if="row.tenant_name"
            class="text-[11px] text-muted-foreground"
          >
            {{ row.tenant_name }}
          </span>
        </div>
      </template>

      <!-- 使用次数列 / Usage count column -->
      <template #usageCount_cell="{ row }">
        <div v-if="row.usage_limit" class="flex flex-col items-end gap-0.5">
          <span class="text-xs text-muted-foreground">
            {{ row.usage_count }} / {{ row.usage_limit }}
          </span>
          <Progress
            :percent="
              Math.min(
                100,
                Math.round((row.usage_count / row.usage_limit) * 100),
              )
            "
            :show-info="false"
            :stroke-color="
              row.usage_count / row.usage_limit >= 0.9
                ? 'hsl(var(--destructive))'
                : row.usage_count / row.usage_limit >= 0.7
                  ? 'hsl(var(--warning))'
                  : 'hsl(var(--success))'
            "
            size="small"
            class="w-24"
          />
        </div>
        <span v-else class="text-muted-foreground">
          {{ row.usage_count }}
        </span>
      </template>

      <!-- 过期时间列 / Expires at column -->
      <template #expiresAt_cell="{ row }">
        <template v-if="row.expires_at">
          <Tooltip :title="formatDate(row.expires_at)">
            <span
              class="text-sm"
              :class="
                new Date(row.expires_at) < new Date()
                  ? 'text-destructive'
                  : new Date(row.expires_at) <
                      new Date(Date.now() + 7 * 86400000)
                    ? 'text-warning'
                    : 'text-muted-foreground'
              "
            >
              {{ formatRelativeTime(row.expires_at) }}
            </span>
          </Tooltip>
        </template>
        <span v-else class="text-muted-foreground">-</span>
      </template>

      <!-- 创建时间列 / Created at column -->
      <template #createdAt_cell="{ row }">
        <Tooltip :title="formatDate(row.created_at)">
          <span class="text-muted-foreground">
            {{ formatRelativeTime(row.created_at) }}
          </span>
        </Tooltip>
      </template>

      <!-- 启用状态列 / Active status column -->
      <template #isActive_cell="{ row }">
        <Switch
          v-access:code="['ai_api_key:toggle_status']"
          :checked="row.is_active"
          :checked-children="$t('admin.common.enabled')"
          :un-checked-children="$t('admin.common.disabled')"
          size="small"
          @change="() => onToggleActive(row)"
        />
      </template>

      <!-- 可用状态列 / Available status column -->
      <template #isAvailable_cell="{ row }">
        <div class="flex items-center justify-center gap-1">
          <Switch
            :checked="row.is_available"
            :checked-children="$t('admin.ai.apiKey.available')"
            :un-checked-children="$t('admin.ai.apiKey.unavailable')"
            size="small"
            disabled
          />
          <Tooltip
            v-if="
              row.expires_at &&
              new Date(row.expires_at) < new Date(Date.now() + 7 * 86400000)
            "
            :title="`${$t('admin.ai.apiKey.expiresAt')}: ${formatDate(
              row.expires_at,
            )}`"
          >
            <IconifyIcon
              icon="lucide:alert-triangle"
              class="size-3.5 text-warning"
            />
          </Tooltip>
        </div>
      </template>
    </Grid>
  </Page>
</template>
