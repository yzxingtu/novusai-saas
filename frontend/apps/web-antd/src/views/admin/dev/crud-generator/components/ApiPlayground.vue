<script setup lang="ts">
/**
 * ApiPlayground — API 测试面板
 *
 * 根据 CrudConfig 生成 API 端点列表,
 * 支持发送测试请求 (模拟), 显示请求/响应。
 */
import { computed, ref } from 'vue';

import {
  Button,
  Card,
  Input,
  Select,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
}>();

type HttpMethod = 'DELETE' | 'GET' | 'POST' | 'PUT';

interface ApiEndpoint {
  method: HttpMethod;
  path: string;
  description: string;
  color: string;
}

const endpoints = computed<ApiEndpoint[]>(() => {
  const module = props.config.module;
  const scope = props.config.scope === 'admin' ? 'admin' : 'tenant';
  const base = `/api/${scope}/${module}s`;

  const eps: ApiEndpoint[] = [
    { method: 'GET', path: base, description: $t(`${T}.apiPlayground.listAll`), color: 'green' },
    { method: 'POST', path: base, description: $t(`${T}.apiPlayground.create`), color: 'blue' },
    { method: 'GET', path: `${base}/{id}`, description: $t(`${T}.apiPlayground.getById`), color: 'green' },
    { method: 'PUT', path: `${base}/{id}`, description: $t(`${T}.apiPlayground.update`), color: 'orange' },
    { method: 'DELETE', path: `${base}/{id}`, description: $t(`${T}.apiPlayground.delete`), color: 'red' },
  ];

  if (props.config.recyclable) {
    eps.push(
      { method: 'GET', path: `${base}/recycle-bin`, description: $t(`${T}.apiPlayground.recycleBinList`), color: 'green' },
      { method: 'POST', path: `${base}/recycle-bin/{id}/restore`, description: $t(`${T}.apiPlayground.restore`), color: 'blue' },
    );
  }

  return eps;
});

const selectedEndpoint = ref(0);
const requestBody = ref('{\n  \n}');
const responseBody = ref('');
const responseStatus = ref<number | null>(null);
const isLoading = ref(false);

const currentEndpoint = computed(() => endpoints.value[selectedEndpoint.value]);

const methodOptions = computed(() =>
  endpoints.value.map((ep, idx) => ({
    label: `${ep.method} ${ep.path}`,
    value: idx,
  })),
);

async function sendRequest() {
  isLoading.value = true;
  responseBody.value = '';
  responseStatus.value = null;

  await new Promise((r) => setTimeout(r, 500));

  const ep = currentEndpoint.value;
  if (!ep) return;

  if (ep.method === 'GET') {
    responseStatus.value = 200;
    responseBody.value = JSON.stringify({
      items: [{ id: 1, name: 'Sample' }],
      total: 1,
      page: 1,
      page_size: 20,
    }, null, 2);
  } else if (ep.method === 'POST') {
    responseStatus.value = 201;
    responseBody.value = JSON.stringify({
      data: { id: 1, ...JSON.parse(requestBody.value || '{}') },
    }, null, 2);
  } else if (ep.method === 'PUT') {
    responseStatus.value = 200;
    responseBody.value = JSON.stringify({
      data: { id: 1, ...JSON.parse(requestBody.value || '{}') },
    }, null, 2);
  } else if (ep.method === 'DELETE') {
    responseStatus.value = 200;
    responseBody.value = JSON.stringify({ message: 'Deleted successfully' }, null, 2);
  }

  isLoading.value = false;
}
</script>

<template>
  <Card size="small">
    <div class="space-y-3">
      <!-- Endpoint selector -->
      <div class="flex gap-2">
        <Select
          v-model:value="selectedEndpoint"
          :options="methodOptions"
          class="flex-1"
          size="small"
        />
        <Button :loading="isLoading" size="small" type="primary" @click="sendRequest">
          Send
        </Button>
      </div>

      <!-- Current endpoint info -->
      <div v-if="currentEndpoint" class="flex items-center gap-2 text-sm">
        <Tag :color="currentEndpoint.color">{{ currentEndpoint.method }}</Tag>
        <code class="text-xs">{{ currentEndpoint.path }}</code>
        <span class="text-muted-foreground text-xs">{{ currentEndpoint.description }}</span>
      </div>

      <!-- Request body -->
      <div v-if="currentEndpoint?.method === 'POST' || currentEndpoint?.method === 'PUT'">
        <p class="text-muted-foreground mb-1 text-xs">Request Body</p>
        <Input.TextArea
          v-model:value="requestBody"
          :auto-size="{ minRows: 4, maxRows: 10 }"
          class="font-mono text-xs"
        />
      </div>

      <!-- Response -->
      <div v-if="responseStatus !== null">
        <div class="mb-1 flex items-center gap-2">
          <span class="text-xs font-medium">Response</span>
          <Tag :color="responseStatus < 300 ? 'green' : 'red'">
            {{ responseStatus }}
          </Tag>
        </div>
        <pre class="bg-accent/30 overflow-auto rounded-md p-3 font-mono text-xs" style="max-height: 300px">{{ responseBody }}</pre>
      </div>
    </div>
  </Card>
</template>
