<script lang="ts" setup>
/**
 * 租户端可用模型列表页面（只读）
 */
import type { TenantAIModelInfo } from '#/api/tenant/ai';

defineOptions({ name: 'TenantAIModelList' });

import { computed, onMounted, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Card, Empty, Input, Pagination, Spin, Tag } from 'ant-design-vue';

import { getTenantAIModelsApi } from '#/api/tenant/ai';
import { $t } from '#/locales';

import { formatPrice, formatTokens, getModelTypeText } from './data';

const loading = ref(false);
const models = ref<TenantAIModelInfo[]>([]);
const searchText = ref('');

// Pagination
const currentPage = ref(1);
const pageSize = ref(12);

async function loadModels() {
  loading.value = true;
  try {
    models.value = await getTenantAIModelsApi();
  } catch {
    // Error handled by request interceptor
  } finally {
    loading.value = false;
  }
}

const filteredModels = computed(() => {
  if (!searchText.value) return models.value;
  const keyword = searchText.value.toLowerCase();
  return models.value.filter(
    (m) =>
      m.name.toLowerCase().includes(keyword) ||
      (m.provider_name && m.provider_name.toLowerCase().includes(keyword)),
  );
});

// Paginated models for current page
const paginatedModels = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return filteredModels.value.slice(start, end);
});

// Reset to first page when search changes
function onSearch() {
  currentPage.value = 1;
}

onMounted(loadModels);
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 搜索栏 -->
    <Card :body-style="{ padding: '12px 16px' }">
      <div class="flex items-center gap-3">
        <Input
          v-model:value="searchText"
          :placeholder="$t('tenant.ai.model.placeholder.searchName')"
          allow-clear
          class="max-w-[300px]"
          @change="onSearch"
        >
          <template #prefix>
            <IconifyIcon icon="lucide:search" class="size-4 text-muted-foreground" />
          </template>
        </Input>
        <span class="text-sm text-muted-foreground">
          {{ filteredModels.length }} {{ $t('tenant.ai.model.title') }}
        </span>
      </div>
    </Card>

    <!-- 模型卡片网格 -->
    <Spin :spinning="loading">
      <div v-if="filteredModels.length > 0" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card
          v-for="model in paginatedModels"
          :key="model.id"
          class="transition-shadow duration-200 hover:shadow-md"
          :body-style="{ padding: '16px' }"
        >
          <!-- 头部：模型名称 + 类型 -->
          <div class="mb-3 flex items-start justify-between">
            <div class="flex items-center gap-2">
              <div class="flex size-9 items-center justify-center rounded-lg bg-primary/10">
                <IconifyIcon icon="lucide:brain" class="size-4.5 text-primary" />
              </div>
              <div>
                <div class="font-medium text-foreground">{{ model.name }}</div>
                <div class="text-xs text-muted-foreground">{{ model.provider_name }}</div>
              </div>
            </div>
            <Tag
              :color="model.type === 'chat' ? 'blue' : model.type === 'embedding' ? 'green' : 'orange'"
              class="ml-2"
            >
              {{ getModelTypeText(model.type) }}
            </Tag>
          </div>

          <!-- 参数信息 -->
          <div class="mb-3 grid grid-cols-2 gap-2 text-sm">
            <div>
              <span class="text-muted-foreground">{{ $t('tenant.ai.model.contextWindow') }}:</span>
              <span class="ml-1 font-medium">{{ formatTokens(model.context_window) }}</span>
            </div>
            <div>
              <span class="text-muted-foreground">{{ $t('tenant.ai.model.inputPrice') }}:</span>
              <span class="ml-1 font-medium">{{ formatPrice(model.input_price_per_1k) }}</span>
            </div>
            <div>
              <span class="text-muted-foreground">{{ $t('tenant.ai.model.outputPrice') }}:</span>
              <span class="ml-1 font-medium">{{ formatPrice(model.output_price_per_1k) }}</span>
            </div>
          </div>

          <!-- 能力标签 -->
          <div class="flex flex-wrap gap-1.5">
            <Tag v-if="model.supports_function_calling" color="purple">
              {{ $t('tenant.ai.model.capability.functionCalling') }}
            </Tag>
            <Tag v-if="model.supports_vision" color="cyan">
              {{ $t('tenant.ai.model.capability.vision') }}
            </Tag>
            <Tag v-if="model.supports_streaming" color="geekblue">
              {{ $t('tenant.ai.model.capability.streaming') }}
            </Tag>
          </div>
        </Card>
      </div>
      <Empty v-else :description="$t('common.noData')" class="py-16" />

      <!-- Pagination -->
      <div v-if="filteredModels.length > pageSize" class="mt-4 flex justify-end">
        <Pagination
          v-model:current="currentPage"
          v-model:page-size="pageSize"
          :total="filteredModels.length"
          :page-size-options="['12', '24', '48']"
          show-size-changer
          show-quick-jumper
          size="small"
        />
      </div>
    </Spin>
  </div>
</template>
