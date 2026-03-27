<script lang="ts" setup>
import type { TableColumnsType } from 'ant-design-vue';

/**
 * 企业端 AI 可用模型列表（只读）
 * Tenant AI available models list (read-only)
 */
import type { TenantAIModelInfo } from '#/api/tenant/ai';

import { onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Card, Spin, Table, Tag } from 'ant-design-vue';

import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { $t } from '#/locales';

defineOptions({ name: 'TenantAIModels' });

const loading = ref(true);
const models = ref<TenantAIModelInfo[]>([]);

async function loadModels() {
  loading.value = true;
  try {
    models.value = await getTenantAIModelsApi();
  } catch {
    models.value = [];
  } finally {
    loading.value = false;
  }
}

function formatTokens(num: null | number | undefined): string {
  if (!num) return '-';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(0)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(0)}K`;
  return `${num}`;
}

function formatPrice(price: null | number | undefined): string {
  if (price === null || price === undefined) return '-';
  return `$${price}`;
}

function getModelTypeText(type: string): string {
  const map: Record<string, string> = {
    chat: $t('tenant.ai.model.type_options.chat'),
    embedding: $t('tenant.ai.model.type_options.embedding'),
    image: $t('tenant.ai.model.type_options.image'),
  };
  return map[type] ?? type;
}

const columns: TableColumnsType<TenantAIModelInfo> = [
  {
    title: $t('tenant.ai.model.name'),
    dataIndex: 'name',
    key: 'name',
    width: 200,
  },
  {
    title: $t('tenant.ai.model.code'),
    dataIndex: 'code',
    key: 'code',
    width: 140,
  },
  {
    title: $t('tenant.ai.model.type'),
    dataIndex: 'type',
    key: 'type',
    width: 90,
  },
  {
    title: $t('tenant.ai.model.providerName'),
    dataIndex: 'provider_name',
    key: 'provider_name',
    width: 120,
  },
  {
    title: $t('tenant.ai.model.contextWindow'),
    dataIndex: 'context_window',
    key: 'context_window',
    width: 100,
  },
  {
    title: $t('tenant.ai.model.inputPrice'),
    dataIndex: 'input_price_per_1k',
    key: 'input_price_per_1k',
    width: 100,
  },
  {
    title: $t('tenant.ai.model.outputPrice'),
    dataIndex: 'output_price_per_1k',
    key: 'output_price_per_1k',
    width: 100,
  },
  {
    title: $t('tenant.ai.model.isActive'),
    dataIndex: 'is_active',
    key: 'is_active',
    width: 80,
    align: 'center' as const,
  },
];

onMounted(loadModels);
</script>

<template>
  <Card class="flex-1" :body-style="{ padding: '16px', height: '100%' }">
    <Spin :spinning="loading">
      <Table
        :columns="columns"
        :data-source="models"
        :pagination="{ pageSize: 20, showSizeChanger: true }"
        :row-key="(r: TenantAIModelInfo) => String(r.id)"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'type'">
            {{ getModelTypeText(record.type) }}
          </template>
          <template v-else-if="column.key === 'context_window'">
            {{ formatTokens(record.context_window) }}
          </template>
          <template v-else-if="column.key === 'input_price_per_1k'">
            {{ formatPrice(record.input_price_per_1k) }}
          </template>
          <template v-else-if="column.key === 'output_price_per_1k'">
            {{ formatPrice(record.output_price_per_1k) }}
          </template>
          <template v-else-if="column.key === 'name'">
            <div class="flex items-center gap-2">
              <div
                class="flex size-8 items-center justify-center rounded-lg"
                :class="record.is_active ? 'bg-primary/10' : 'bg-muted'"
              >
                <IconifyIcon
                  :icon="
                    record.type === 'embedding'
                      ? 'lucide:database'
                      : record.type === 'image'
                        ? 'lucide:image'
                        : 'lucide:brain'
                  "
                  class="size-4"
                  :class="
                    record.is_active ? 'text-primary' : 'text-muted-foreground'
                  "
                />
              </div>
              <div class="flex flex-col gap-0.5">
                <span class="font-medium text-foreground">{{
                  record.name
                }}</span>
                <div
                  v-if="
                    record.supports_function_calling ||
                    record.supports_vision ||
                    record.supports_streaming
                  "
                  class="flex flex-wrap gap-1"
                >
                  <Tag
                    v-if="record.supports_function_calling"
                    class="!mr-0 rounded border-0 bg-blue-500/10 px-1 py-0 text-[10px] text-blue-600"
                  >
                    {{ $t('tenant.ai.model.capability.functionCalling') }}
                  </Tag>
                  <Tag
                    v-if="record.supports_vision"
                    class="!mr-0 rounded border-0 bg-purple-500/10 px-1 py-0 text-[10px] text-purple-600"
                  >
                    {{ $t('tenant.ai.model.capability.vision') }}
                  </Tag>
                  <Tag
                    v-if="record.supports_streaming"
                    class="!mr-0 rounded border-0 bg-green-500/10 px-1 py-0 text-[10px] text-green-600"
                  >
                    {{ $t('tenant.ai.model.capability.streaming') }}
                  </Tag>
                </div>
              </div>
            </div>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <Tag :color="record.is_active ? 'success' : 'default'">
              {{
                record.is_active ? $t('common.enabled') : $t('common.disabled')
              }}
            </Tag>
          </template>
        </template>
      </Table>
    </Spin>
  </Card>
</template>
