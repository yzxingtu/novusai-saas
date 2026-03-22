<script lang="ts" setup>
/**
 * AI API Key 管理列表页面
 * AI API Key management list page
 */
import type { AIApiKeyInfo } from '#/api/admin/ai';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  message,
  Modal,
  Progress,
  Switch,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import { getAIApiKeyListApi, toggleAIApiKeyStatusApi } from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';
import { toAttachmentImageUrl } from '#/utils/image';
import {
  getScopeColor,
  getScopeIcon,
  getScopeText,
} from '#/utils/scope-helpers';

import {
  getFormDefaults,
  useColumns,
  useFormSchema,
  useGridFormSchema,
} from './data';
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

const { Grid, FormDrawer, onRefresh } = useCrudPage<AIApiKeyInfo>({
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
    formSchema: (isEdit?: boolean) => useFormSchema(Boolean(isEdit)),
    entityName: $t('admin.ai.apiKey.name'),
    entityDescription: $t('admin.ai.apiKey.pageDesc'),
  },
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('admin.ai.apiKey.pageDesc')"
    content-class="ai-api-keys-page flex flex-col gap-4"
  >
    <FormDrawer @success="onRefresh" />

    <Grid>
      <!-- 名称列 / Name column -->
      <template #name_cell="{ row }">
        <div class="flex items-start gap-3 py-0.5">
          <div
            class="flex size-10 shrink-0 items-center justify-center rounded-xl border shadow-sm"
            :class="
              row.is_available
                ? 'border-success/20 bg-gradient-to-br from-success/15 to-success/5'
                : 'border-border/80 bg-muted/60'
            "
          >
            <IconifyIcon
              icon="lucide:key-round"
              class="size-[18px]"
              :class="
                row.is_available ? 'text-success' : 'text-muted-foreground'
              "
            />
          </div>
          <div class="flex min-w-0 flex-col gap-1">
            <span class="truncate font-semibold leading-tight text-foreground">
              {{ row.name }}
            </span>
            <Tooltip
              v-if="row.last_used_at"
              :title="formatDate(row.last_used_at)"
            >
              <span
                class="inline-flex w-fit max-w-full cursor-default items-center gap-1.5 rounded-full bg-muted/90 px-2 py-0.5 text-[11px] text-muted-foreground ring-1 ring-border/50"
              >
                <IconifyIcon
                  icon="lucide:clock"
                  class="size-3 shrink-0 opacity-70"
                />
                <span class="shrink-0">{{
                  $t('admin.ai.apiKey.lastUsedRecent')
                }}</span>
                <span class="font-medium tabular-nums text-foreground/80">{{
                  formatRelativeTime(row.last_used_at)
                }}</span>
              </span>
            </Tooltip>
            <span
              v-else
              class="inline-flex w-fit items-center gap-1 rounded-full bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              <IconifyIcon icon="lucide:minus" class="size-3 opacity-50" />
              {{ $t('admin.ai.apiKey.lastUsedNever') }}
            </span>
          </div>
        </div>
      </template>

      <!-- Key 预览列 / Key preview column -->
      <template #keyPreview_cell="{ row }">
        <div
          v-if="row.key_preview"
          class="group flex max-w-full items-center gap-1 rounded-lg border border-border/70 bg-muted/25 py-1 pl-2 pr-1 shadow-sm"
        >
          <code
            class="min-w-0 flex-1 truncate font-mono text-[11px] tracking-wide text-foreground/90"
          >
            {{ row.key_preview }}
          </code>
          <Tooltip :title="$t('admin.ai.apiKey.messages.copy')">
            <Button
              type="text"
              size="small"
              class="!size-7 shrink-0 text-muted-foreground hover:!text-primary"
              @click="onCopyKeyPreview(row.key_preview)"
            >
              <IconifyIcon icon="lucide:copy" class="size-3.5" />
            </Button>
          </Tooltip>
        </div>
        <span v-else class="text-xs text-muted-foreground/80">{{
          $t('admin.common.notSet')
        }}</span>
      </template>

      <!-- 供应商列：图标 + 名称 + 模型数 / Provider column -->
      <template #providerName_cell="{ row }">
        <div v-if="row.provider_name" class="flex items-center gap-2.5 py-0.5">
          <div
            class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border/60 bg-card shadow-sm"
          >
            <img
              v-if="
                toAttachmentImageUrl(row.provider_icon, { preset: 'small' })
              "
              :src="
                toAttachmentImageUrl(row.provider_icon, { preset: 'small' })
              "
              class="size-6 object-contain"
              alt=""
            />
            <IconifyIcon
              v-else
              icon="lucide:cpu"
              class="size-4 text-muted-foreground"
            />
          </div>
          <div class="flex min-w-0 flex-col gap-0.5">
            <span class="truncate font-medium leading-snug text-foreground">
              {{ row.provider_name }}
            </span>
            <span
              v-if="row.provider_model_count > 0"
              class="text-[11px] text-muted-foreground"
            >
              {{
                $t('admin.ai.apiKey.providerModels', {
                  count: row.provider_model_count,
                })
              }}
            </span>
          </div>
        </div>
        <span v-else class="text-xs text-muted-foreground/80">{{
          $t('admin.common.notSet')
        }}</span>
      </template>

      <!-- 作用域列 / Scope column -->
      <template #scope_cell="{ row }">
        <div class="flex flex-col items-start gap-1 py-0.5">
          <Tag
            :color="getScopeColor(row.scope)"
            class="!mr-0 inline-flex items-center gap-1 rounded-md !px-2 !py-0.5 !text-xs !leading-5"
          >
            <IconifyIcon :icon="getScopeIcon(row.scope)" class="size-3.5" />
            <span>{{ getScopeText(row.scope) }}</span>
          </Tag>
          <span
            v-if="row.tenant_name"
            class="line-clamp-2 max-w-[10rem] text-[11px] leading-tight text-muted-foreground"
          >
            {{ row.tenant_name }}
          </span>
        </div>
      </template>

      <!-- 使用次数列 / Usage count column -->
      <template #usageCount_cell="{ row }">
        <div
          v-if="row.usage_limit"
          class="ml-auto flex w-full min-w-[7.5rem] max-w-[9rem] flex-col items-end gap-1"
        >
          <div class="flex w-full items-center justify-end gap-2">
            <span class="text-xs tabular-nums text-muted-foreground">
              {{ row.usage_count }} / {{ row.usage_limit }}
            </span>
            <span
              class="rounded-md bg-muted/80 px-1.5 py-px text-[10px] font-semibold tabular-nums text-foreground/80"
            >
              {{
                Math.min(
                  100,
                  Math.round((row.usage_count / row.usage_limit) * 100),
                )
              }}%
            </span>
          </div>
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
            class="!m-0 w-full [&_.ant-progress-bg]:!rounded-full [&_.ant-progress-inner]:!rounded-full"
          />
        </div>
        <span
          v-else
          class="text-sm font-medium tabular-nums text-foreground/85"
        >
          {{ row.usage_count }}
        </span>
      </template>

      <!-- 过期时间列 / Expires at column -->
      <template #expiresAt_cell="{ row }">
        <template v-if="row.expires_at">
          <Tooltip :title="formatDate(row.expires_at)">
            <span
              class="inline-flex cursor-default rounded-md px-1.5 py-0.5 text-sm tabular-nums transition-colors hover:bg-muted/80"
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
        <span v-else class="text-xs text-muted-foreground/80">{{
          $t('admin.common.notSet')
        }}</span>
      </template>

      <!-- 创建时间列 / Created at column -->
      <template #createdAt_cell="{ row }">
        <Tooltip :title="formatDate(row.created_at)">
          <span
            class="inline-flex cursor-default rounded-md px-1.5 py-0.5 text-sm tabular-nums text-muted-foreground transition-colors hover:bg-muted/80"
          >
            {{ formatRelativeTime(row.created_at) }}
          </span>
        </Tooltip>
      </template>

      <!-- 启用状态列 / Active status column -->
      <template #isActive_cell="{ row }">
        <div class="flex justify-center py-0.5">
          <Switch
            v-access:code="['ai_api_key:toggle_status']"
            :checked="row.is_active"
            :checked-children="$t('admin.common.enabled')"
            :un-checked-children="$t('admin.common.disabled')"
            size="small"
            @change="() => onToggleActive(row)"
          />
        </div>
      </template>

      <!-- 可用状态列 / Available status column -->
      <template #isAvailable_cell="{ row }">
        <div class="flex items-center justify-center gap-1.5 py-0.5">
          <Switch
            :checked="row.is_available"
            :checked-children="$t('admin.ai.apiKey.available')"
            :un-checked-children="$t('admin.ai.apiKey.unavailable')"
            size="small"
            disabled
            class="opacity-95"
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
            <span
              class="inline-flex size-7 items-center justify-center rounded-md bg-warning/10 text-warning ring-1 ring-warning/25"
            >
              <IconifyIcon icon="lucide:alert-triangle" class="size-3.5" />
            </span>
          </Tooltip>
        </div>
      </template>
    </Grid>
  </Page>
</template>

<style scoped>
/* 表格行垂直节奏：避免单元格贴顶显得拥挤 / Row vertical rhythm */
.ai-api-keys-page :deep(.vxe-body--row .vxe-cell) {
  padding-top: 10px;
  padding-bottom: 10px;
}
</style>
