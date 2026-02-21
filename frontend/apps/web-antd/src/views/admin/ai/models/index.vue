<script lang="ts" setup>
/**
 * AI 模型管理列表页面
 */
import type { AIModelInfo } from '#/api/admin/ai';

defineOptions({ name: 'AIModelList' });

import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Card, message, Modal, Switch, Tag, Tooltip } from 'ant-design-vue';

import { useCrudPage } from '#/adapter/vxe-table';
import {
  getAIModelListApi,
  testAIGatewayApi,
  toggleAIModelStatusApi,
} from '#/api/admin/ai';
import { $t } from '#/locales';

import { getFormDefaults, getModelTypeText, useColumns, useGridFormSchema } from './data';
import Form from './modules/form.vue';

/**
 * 格式化 Token 数量
 */
function formatTokens(num: null | number | undefined): string {
  if (!num) return '-';
  if (num >= 1000000) return `${(num / 1000000).toFixed(0)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return `${num}`;
}

/**
 * 格式化价格
 */
function formatPrice(price: null | number | undefined): string {
  if (price === null || price === undefined) return '-';
  return `$${price}`;
}

function onToggleModelActive(row: AIModelInfo) {
  Modal.confirm({
    title: row.is_active
      ? $t('admin.ai.model.messages.confirmDisable')
      : $t('admin.ai.model.messages.confirmEnable'),
    onOk: async () => {
      try {
        await toggleAIModelStatusApi(row.id);
        message.success($t('admin.ai.model.messages.toggleSuccess'));
        onRefresh();
      } catch {
        // handled by interceptor
      }
    },
  });
}

/** 正在测试中的模型 ID 集合 */
const testingModelIds = ref<Set<number>>(new Set());

/**
 * 测试模型连通性
 */
async function onTestModel(row: AIModelInfo) {
  if (testingModelIds.value.has(row.id)) return;

  testingModelIds.value.add(row.id);
  const hideLoading = message.loading($t('admin.ai.model.testing'), 0);

  try {
    const result = await testAIGatewayApi({
      provider_id: row.provider_id,
      model_code: row.code,
    });

    if (result.connected) {
      message.success(
        $t('admin.ai.model.testSuccess', { latency: result.latency_ms }),
      );
    } else {
      message.error(
        $t('admin.ai.model.testFailed', {
          error: result.error || $t('common.requestFailed'),
        }),
      );
    }
  } catch {
    message.error(
      $t('admin.ai.model.testFailed', { error: $t('common.requestFailed') }),
    );
  } finally {
    hideLoading();
    testingModelIds.value.delete(row.id);
  }
}

const { Grid, FormDrawer, onRefresh } =
  useCrudPage<AIModelInfo>({
    api: {
      list: getAIModelListApi,
      resource: '/admin/ai/models',
    },
    columns: useColumns,
    searchSchema: useGridFormSchema(),
    formComponent: Form,
    formDefaults: getFormDefaults,
    i18nPrefix: 'admin.ai.model',
    nameField: 'name',
    defaultSort: '-created_at',
    recycleBin: true,
    createPermission: 'ai_model:create',
    customActions: {
      test: onTestModel,
    },
  });
</script>

<template>
  <Page auto-content-height :description="$t('admin.ai.model.pageDesc')" content-class="flex flex-col gap-4">
    <FormDrawer @success="onRefresh" />

    <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
      <Grid>
        <!-- 名称列：图标 + 名称 + 能力徽章 -->
        <template #name_cell="{ row }">
          <div class="flex items-center gap-2">
            <div
              class="flex size-8 items-center justify-center rounded-lg"
              :class="row.is_active ? 'bg-primary/10' : 'bg-muted'"
            >
              <IconifyIcon
                :icon="row.type === 'embedding' ? 'lucide:database' : row.type === 'image' ? 'lucide:image' : 'lucide:brain'"
                class="size-4"
                :class="row.is_active ? 'text-primary' : 'text-muted-foreground'"
              />
            </div>
            <div class="flex flex-col gap-0.5">
              <span class="font-medium text-foreground">{{ row.name }}</span>
              <div class="flex flex-wrap gap-1">
                <Tag
                  v-if="row.supports_function_calling"
                  class="!mr-0 rounded border-0 bg-blue-500/10 px-1 py-0 text-[10px] text-blue-600"
                >
                  {{ $t('admin.ai.model.functionCalling') }}
                </Tag>
                <Tag
                  v-if="row.supports_vision"
                  class="!mr-0 rounded border-0 bg-purple-500/10 px-1 py-0 text-[10px] text-purple-600"
                >
                  {{ $t('admin.ai.model.vision') }}
                </Tag>
                <Tag
                  v-if="row.supports_streaming"
                  class="!mr-0 rounded border-0 bg-green-500/10 px-1 py-0 text-[10px] text-green-600"
                >
                  {{ $t('admin.ai.model.streaming') }}
                </Tag>
              </div>
            </div>
          </div>
        </template>

        <!-- 代码列 -->
        <template #code_cell="{ row }">
          <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
            {{ row.code }}
          </code>
        </template>

        <!-- 类型列 -->
        <template #type_cell="{ row }">
          <Tag
            :color="
              row.type === 'chat'
                ? 'blue'
                : row.type === 'embedding'
                  ? 'green'
                  : 'orange'
            "
          >
            {{ getModelTypeText(row.type) }}
          </Tag>
        </template>

        <!-- 上下文窗口列 -->
        <template #contextWindow_cell="{ row }">
          <Tooltip v-if="row.context_window" :title="row.context_window.toLocaleString() + ' tokens'">
            <span class="font-mono text-sm text-muted-foreground">
              {{ formatTokens(row.context_window) }}
            </span>
          </Tooltip>
          <span v-else class="text-muted-foreground">-</span>
        </template>

        <!-- 合并价格列 -->
        <template #price_cell="{ row }">
          <div class="flex flex-col items-center gap-0.5 text-xs">
            <span class="text-muted-foreground">
              <span class="text-green-600">{{ formatPrice(row.input_price_per_1k) }}</span>
              /
              <span class="text-orange-600">{{ formatPrice(row.output_price_per_1k) }}</span>
            </span>
          </div>
        </template>

        <!-- 启用状态列：Switch -->
        <template #isActive_cell="{ row }">
          <Switch
            v-access:code="['ai_model:toggle_status']"
            :checked="row.is_active"
            size="small"
            @change="() => onToggleModelActive(row)"
          />
        </template>
      </Grid>
    </Card>
  </Page>
</template>
