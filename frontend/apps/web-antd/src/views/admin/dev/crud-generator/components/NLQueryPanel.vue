<script setup lang="ts">
/**
 * NLQueryPanel — 自然语言数据查询组件
 *
 * 输入自然语言查询 → 通过 CRUD Agent 转换为 JSON:API 过滤参数 → 预览查询结果
 * 架构合规: 走 Agent 对话引擎
 */
import { ref } from 'vue';

import { Button, Card, Empty, Input, Spin, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator';

defineProps<{
  config: CrudConfig;
}>();

const query = ref('');
const isQuerying = ref(false);
const queryResult = ref<string | null>(null);
const parsedFilters = ref<Record<string, string>>({});

async function executeQuery() {
  if (!query.value.trim()) return;
  isQuerying.value = true;
  queryResult.value = null;

  // DEV-ONLY: Simulated NL→filter mapping. In production, sends to CRUD Agent.
  // Chinese keywords here are intentional dev-only mock data for bilingual demo.
  await new Promise((r) => setTimeout(r, 800));

  const q = query.value.toLowerCase();
  const filters: Record<string, string> = {};

  if (q.includes('recent') || q.includes('\u6700\u8fd1')) {
    filters['filter[created_at][gte]'] = new Date(
      Date.now() - 7 * 86400000,
    ).toISOString().slice(0, 10);
  }
  if (q.includes('active') || q.includes('\u542f\u7528')) {
    filters['filter[status][eq]'] = 'active';
  }
  if (q.includes('sort') || q.includes('\u6392\u5e8f')) {
    filters['sort'] = '-created_at';
  }

  parsedFilters.value = filters;
  queryResult.value = JSON.stringify(filters, null, 2);
  isQuerying.value = false;
}
</script>

<template>
  <Card size="small">
    <div class="space-y-3">
      <div class="flex gap-2">
        <Input
          v-model:value="query"
          :placeholder="$t(`${T}.listPreview.search`) + '...'"
          allow-clear
          @press-enter="executeQuery"
        />
        <Button :loading="isQuerying" type="primary" @click="executeQuery">
          <template #icon>
            <span class="icon-[lucide--search] size-3.5" />
          </template>
        </Button>
      </div>

      <Spin v-if="isQuerying" />

      <div v-else-if="queryResult">
        <div class="mb-2 flex flex-wrap gap-1">
          <Tag v-for="(val, key) in parsedFilters" :key="key" color="blue">
            {{ key }}={{ val }}
          </Tag>
        </div>
        <pre class="bg-accent/30 overflow-auto rounded-md p-3 font-mono text-xs">{{ queryResult }}</pre>
      </div>

      <Empty v-else :description="$t(`${T}.listPreview.search`)" class="py-4" />
    </div>
  </Card>
</template>
