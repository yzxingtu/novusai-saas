<script lang="ts" setup>
/**
 * AI API Key 管理列表页面
 */
import type { AIApiKeyInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIApiKeyList' });

import { Page } from '@vben/common-ui';
import { IconifyIcon, Plus } from '@vben/icons';

import { Badge, Card, message, Modal, Progress, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAIApiKeyListApi,
  toggleAIApiKeyStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { getFormDefaults, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

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
        // Error handled by request interceptor
      }
    },
  });
}

const { Grid, FormDrawer, onCreate, onRefresh } =
  useCrudPage<AIApiKeyInfo>({
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
  });
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg"
              :class="row.is_available ? 'bg-success/10' : 'bg-muted'"
            >
              <IconifyIcon
                icon="lucide:key"
                class="size-4"
                :class="row.is_available ? 'text-success' : 'text-muted-foreground'"
              />
            </div>
            <div class="flex flex-col">
              <span class="font-medium text-foreground">{{ row.name }}</span>
              <Tooltip v-if="row.last_used_at" :title="formatDate(row.last_used_at)">
                <span class="text-xs text-muted-foreground">
                  {{ $t('admin.ai.apiKey.lastUsedAt') }}: {{ formatRelativeTime(row.last_used_at) }}
                </span>
              </Tooltip>
            </div>
          </div>
        </template>

        <!-- Key 预览列 -->
        <template #keyPreview_cell="{ row }">
          <code
            v-if="row.key_preview"
            class="rounded bg-accent px-1.5 py-0.5 text-xs"
          >
            {{ row.key_preview }}
          </code>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 租户列 -->
        <template #tenantName_cell="{ row }">
          <Tag v-if="row.tenant_name" color="orange">
            {{ row.tenant_name }}
          </Tag>
          <Tag v-else color="blue">
            {{ $t('admin.ai.apiKey.scope.platform') }}
          </Tag>
        </template>

        <!-- 使用次数列：进度条 -->
        <template #usageCount_cell="{ row }">
          <div v-if="row.usage_limit" class="flex flex-col items-end gap-0.5">
            <span class="text-xs text-muted-foreground">
              {{ row.usage_count }} / {{ row.usage_limit }}
            </span>
            <Progress
              :percent="Math.min(100, Math.round((row.usage_count / row.usage_limit) * 100))"
              :show-info="false"
              :stroke-color="(row.usage_count / row.usage_limit) >= 0.9 ? '#ef4444' : (row.usage_count / row.usage_limit) >= 0.7 ? '#f59e0b' : '#22c55e'"
              size="small"
              class="w-20"
            />
          </div>
          <span v-else class="text-muted-foreground">
            {{ row.usage_count }}
          </span>
        </template>

        <!-- 启用状态列 -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['ai_api_key:toggle_status']"
            :checked="row.is_active"
            size="small"
            @change="() => onToggleActive(row)"
          />
        </template>

        <!-- 可用状态列：圆点 + 过期警告 -->
        <template #isAvailable_cell="{ row }">
          <div class="flex items-center justify-center gap-1">
            <Badge :status="row.is_available ? 'success' : 'error'" />
            <Tooltip
              v-if="row.expires_at && new Date(row.expires_at) < new Date(Date.now() + 7 * 86400000)"
              :title="$t('admin.ai.apiKey.expiresAt') + ': ' + formatDate(row.expires_at)"
            >
              <IconifyIcon
                icon="lucide:alert-triangle"
                class="size-3.5 text-warning"
              />
            </Tooltip>
          </div>
        </template>

        <!-- 工具栏 -->
        <template #toolbar-tools>
          <Card
            v-access:code="['ai_api_key:create']"
            size="small"
            class="mr-2 cursor-pointer transition-shadow duration-200 hover:shadow-md"
            @click="onCreate"
          >
            <div class="flex items-center gap-2 text-primary">
              <Plus class="size-4" />
              <span class="font-medium">{{
                $t('admin.ai.apiKey.create')
              }}</span>
            </div>
          </Card>
        </template>
      </Grid>
    </Card>
  </Page>
</template>
